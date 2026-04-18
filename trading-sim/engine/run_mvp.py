from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pyodbc

CURRENT_DIR = Path(__file__).resolve().parent
TRADING_SIM_DIR = CURRENT_DIR.parent
REPO_ROOT = TRADING_SIM_DIR.parent
STRATEGIES_DIR = TRADING_SIM_DIR / "strategies"

for path in (CURRENT_DIR, STRATEGIES_DIR):
    p = str(path)
    if p not in sys.path:
        sys.path.append(p)

from models import MarketOrder, PositionState  # noqa: E402
from pricing import generate_price_grid  # noqa: E402
from simulator import TradingSimulator, build_daily_snapshots  # noqa: E402
from rotation_strategy import RotationStrategy  # noqa: E402


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def db_connect() -> pyodbc.Connection:
    driver = require_env("SQL_DRIVER")
    server = require_env("SQL_SERVER")
    database = require_env("SQL_DATABASE")
    auth_mode = os.getenv("SQL_AUTH_MODE", "sql").lower().strip()

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
        "TrustServerCertificate=yes",
    ]

    if auth_mode == "windows":
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={require_env('SQL_USER')}")
        parts.append(f"PWD={require_env('SQL_PASSWORD')}")

    return pyodbc.connect(";".join(parts))


def ensure_dim_date(conn: pyodbc.Connection, all_days: list[date]) -> None:
    sql = """
IF NOT EXISTS (SELECT 1 FROM dbo.DimDate WHERE DateKey = ?)
BEGIN
    INSERT INTO dbo.DimDate (
        DateKey, FullDate, CalendarYear, CalendarMonth, CalendarDay,
        MonthName, QuarterNumber, WeekOfYear, IsMonthEnd
    )
    VALUES (?, ?, ?, ?, ?, DATENAME(MONTH, ?), DATEPART(QUARTER, ?), DATEPART(ISO_WEEK, ?),
        CASE WHEN EOMONTH(?) = ? THEN 1 ELSE 0 END)
END
"""
    rows = []
    for d in all_days:
        dk = int(d.strftime("%Y%m%d"))
        rows.append((dk, dk, d, d.year, d.month, d.day, d, d, d, d, d))

    cur = conn.cursor()
    cur.fast_executemany = True
    cur.executemany(sql, rows)
    conn.commit()


def ensure_portfolio(conn: pyodbc.Connection, portfolio_code: str) -> int:
    cur = conn.cursor()
    cur.execute(
        """
IF NOT EXISTS (SELECT 1 FROM dbo.DimPortfolio WHERE PortfolioCode = ?)
BEGIN
    INSERT INTO dbo.DimPortfolio (PortfolioCode, PortfolioName, BaseCurrency, RiskProfile, InceptionDate)
    VALUES (?, ?, 'USD', 'Balanced', CAST(GETDATE() AS date))
END
""",
        portfolio_code,
        portfolio_code,
        f"{portfolio_code} Portfolio",
    )
    conn.commit()

    cur.execute("SELECT PortfolioKey FROM dbo.DimPortfolio WHERE PortfolioCode = ?", portfolio_code)
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Portfolio not found: {portfolio_code}")
    return int(row[0])


def ensure_securities(conn: pyodbc.Connection, tickers: list[str]) -> dict[str, int]:
    security_info = {
        "AAPL": ("Apple Inc.", "Equity", "USD"),
        "MSFT": ("Microsoft Corp.", "Equity", "USD"),
        "SPY": ("SPDR S&P 500 ETF", "ETF", "USD"),
    }

    cur = conn.cursor()
    for ticker in tickers:
        name, asset_class, ccy = security_info.get(ticker, (ticker, "Unknown", "USD"))
        cur.execute(
            """
IF NOT EXISTS (SELECT 1 FROM dbo.DimSecurity WHERE Ticker = ?)
BEGIN
    INSERT INTO dbo.DimSecurity (Ticker, SecurityName, AssetClass, CurrencyCode)
    VALUES (?, ?, ?, ?)
END
""",
            ticker,
            ticker,
            name,
            asset_class,
            ccy,
        )
    conn.commit()

    placeholders = ",".join("?" for _ in tickers)
    cur.execute(f"SELECT Ticker, SecurityKey FROM dbo.DimSecurity WHERE Ticker IN ({placeholders})", tickers)
    mapping = {str(r[0]): int(r[1]) for r in cur.fetchall()}

    missing = [t for t in tickers if t not in mapping]
    if missing:
        raise RuntimeError(f"Missing securities in DimSecurity: {missing}")
    return mapping


def purge_previous_run(
    conn: pyodbc.Connection,
    portfolio_key: int,
    strategy_code: str,
    date_keys: list[int],
) -> None:
    if not date_keys:
        return
    placeholders = ",".join("?" for _ in date_keys)
    cur = conn.cursor()
    cur.execute(
        f"DELETE FROM dbo.FactTrades WHERE PortfolioKey = ? AND StrategyCode = ? AND TradeDateKey IN ({placeholders})",
        [portfolio_key, strategy_code, *date_keys],
    )
    cur.execute(
        f"DELETE FROM dbo.PortfolioPositionsDaily WHERE PortfolioKey = ? AND DateKey IN ({placeholders})",
        [portfolio_key, *date_keys],
    )
    conn.commit()


def insert_results(
    conn: pyodbc.Connection,
    portfolio_key: int,
    security_map: dict[str, int],
    trades,
    snapshots,
) -> None:
    trade_rows = []
    for t in trades:
        trade_rows.append(
            (
                int(t.trade_date.strftime("%Y%m%d")),
                None,
                portfolio_key,
                security_map[t.ticker],
                t.side,
                float(t.quantity),
                float(t.execution_price),
                float(t.fee_amount),
                float(t.slippage_amount),
                "USD",
                t.strategy_code,
                t.order_type,
            )
        )

    snapshot_rows = []
    for s in snapshots:
        snapshot_rows.append(
            (
                int(s.snapshot_date.strftime("%Y%m%d")),
                portfolio_key,
                security_map[s.ticker],
                float(s.quantity),
                float(s.avg_cost),
                float(s.market_value),
                float(s.unrealized_pnl),
                float(s.weight_pct),
            )
        )

    cur = conn.cursor()
    if trade_rows:
        cur.fast_executemany = True
        cur.executemany(
            """
INSERT INTO dbo.FactTrades (
    TradeDateKey, SettleDateKey, PortfolioKey, SecurityKey,
    Side, Quantity, Price, FeeAmount, SlippageAmount,
    CurrencyCode, StrategyCode, OrderType
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""",
            trade_rows,
        )

    if snapshot_rows:
        cur.fast_executemany = True
        cur.executemany(
            """
INSERT INTO dbo.PortfolioPositionsDaily (
    DateKey, PortfolioKey, SecurityKey, Quantity, AvgCost,
    MarketValue, UnrealizedPnL, WeightPct
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""",
            snapshot_rows,
        )

    conn.commit()


def run_simulation(start_date: date, days: int, fee_bps: float, slippage_bps: float) -> tuple[list, list, list[date]]:
    tickers = ["AAPL", "MSFT", "SPY"]
    calendar, prices = generate_price_grid(tickers=tickers, start_date=start_date, days=days)

    sim = TradingSimulator(fee_bps=fee_bps, slippage_bps=slippage_bps)
    strategy = RotationStrategy(strategy_code="SIM_MVP")
    positions = {ticker: PositionState() for ticker in tickers}

    executed_trades = []
    all_snapshots = []

    for day_idx, day in enumerate(calendar):
        day_prices = prices[day]
        orders: list[MarketOrder] = strategy.build_orders(
            day_index=day_idx,
            trade_date=day,
            prices=day_prices,
            positions=positions,
        )

        for order in orders:
            px = day_prices[order.ticker]
            trade = sim.execute_market_order(order, px, positions[order.ticker])
            executed_trades.append(trade)

        day_snapshots = build_daily_snapshots(day, positions, day_prices)
        all_snapshots.extend(day_snapshots)

    return executed_trades, all_snapshots, calendar


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run trading simulator MVP for 60 days")
    parser.add_argument("--start-date", default="2026-01-05", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=60, help="Number of business days to simulate")
    parser.add_argument("--fee-bps", type=float, default=5.0, help="Fee in basis points")
    parser.add_argument("--slippage-bps", type=float, default=3.0, help="Slippage in basis points")
    parser.add_argument("--portfolio-code", default="MAIN", help="Portfolio code in DimPortfolio")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")

    start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    trades, snapshots, calendar = run_simulation(
        start_date=start,
        days=args.days,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
    )

    with db_connect() as conn:
        ensure_dim_date(conn, calendar)
        portfolio_key = ensure_portfolio(conn, args.portfolio_code)
        security_map = ensure_securities(conn, ["AAPL", "MSFT", "SPY"])

        date_keys = [int(d.strftime("%Y%m%d")) for d in calendar]
        purge_previous_run(conn, portfolio_key, "SIM_MVP", date_keys)
        insert_results(conn, portfolio_key, security_map, trades, snapshots)

    print(f"Simulation complete: days={len(calendar)} trades={len(trades)} snapshots={len(snapshots)}")
    print("Stored outputs in dbo.FactTrades and dbo.PortfolioPositionsDaily")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import math
import os
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypeVar

import pyodbc


REPO_ROOT = Path(__file__).resolve().parents[1]
RowT = TypeVar("RowT")


@dataclass
class DailyPerformance:
    date_key: int
    nav: float
    daily_pnl: float
    cum_pnl: float
    return_pct: float
    contribution_pct: float


@dataclass
class DailyRisk:
    date_key: int
    volatility20d: float
    max_drawdown: float
    var95: float
    beta: float | None
    sharpe_ratio: float | None


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


def date_to_key(raw: str | None) -> int | None:
    if raw is None:
        return None
    return int(datetime.strptime(raw, "%Y-%m-%d").strftime("%Y%m%d"))


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def resolve_portfolio_key(conn: pyodbc.Connection, portfolio_code: str) -> int:
    cur = conn.cursor()
    cur.execute("SELECT PortfolioKey FROM dbo.DimPortfolio WHERE PortfolioCode = ?", portfolio_code)
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Portfolio code not found in dbo.DimPortfolio: {portfolio_code}")
    return int(row[0])


def fetch_all_dates(
    conn: pyodbc.Connection,
    portfolio_key: int,
    start_date_key: int | None,
    end_date_key: int | None,
) -> list[int]:
    cur = conn.cursor()
    cur.execute(
        """
SELECT DISTINCT DateKey
FROM (
    SELECT DateKey
    FROM dbo.PortfolioPositionsDaily
    WHERE PortfolioKey = ?
    UNION
    SELECT TradeDateKey AS DateKey
    FROM dbo.FactTrades
    WHERE PortfolioKey = ?
) x
WHERE (? IS NULL OR DateKey >= ?)
  AND (? IS NULL OR DateKey <= ?)
ORDER BY DateKey
""",
        portfolio_key,
        portfolio_key,
        start_date_key,
        start_date_key,
        end_date_key,
        end_date_key,
    )
    return [int(r[0]) for r in cur.fetchall()]


def ensure_no_missing_prices(
    conn: pyodbc.Connection,
    portfolio_key: int,
    start_date_key: int | None,
    end_date_key: int | None,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
SELECT TOP 20
    pos.DateKey,
    s.Ticker,
    pos.Quantity
FROM dbo.PortfolioPositionsDaily pos
INNER JOIN dbo.DimSecurity s ON s.SecurityKey = pos.SecurityKey
LEFT JOIN dbo.FactPrice fp
    ON fp.DateKey = pos.DateKey
   AND fp.SecurityKey = pos.SecurityKey
WHERE pos.PortfolioKey = ?
  AND ABS(pos.Quantity) > 0.0000001
  AND (? IS NULL OR pos.DateKey >= ?)
  AND (? IS NULL OR pos.DateKey <= ?)
  AND fp.FactPriceId IS NULL
ORDER BY pos.DateKey, s.Ticker
""",
        portfolio_key,
        start_date_key,
        start_date_key,
        end_date_key,
        end_date_key,
    )
    missing = cur.fetchall()
    if not missing:
        return

    lines = [f"{int(r[0])}:{str(r[1])}" for r in missing]
    raise RuntimeError(
        "Missing close prices in dbo.FactPrice for existing positions. "
        "Load real market data into FactPrice first (for example from "
        "[KHLWorldInvest].[stg].[stg_bourso_price_history]). "
        f"Samples: {', '.join(lines)}"
    )


def fetch_market_values_by_date(
    conn: pyodbc.Connection,
    portfolio_key: int,
    start_date_key: int | None,
    end_date_key: int | None,
) -> dict[int, float]:
    cur = conn.cursor()
    cur.execute(
        """
SELECT
    pos.DateKey,
    SUM(pos.Quantity * fp.ClosePrice) AS MarketValue
FROM dbo.PortfolioPositionsDaily pos
INNER JOIN dbo.FactPrice fp
    ON fp.DateKey = pos.DateKey
   AND fp.SecurityKey = pos.SecurityKey
WHERE pos.PortfolioKey = ?
  AND (? IS NULL OR pos.DateKey >= ?)
  AND (? IS NULL OR pos.DateKey <= ?)
GROUP BY pos.DateKey
ORDER BY pos.DateKey
""",
        portfolio_key,
        start_date_key,
        start_date_key,
        end_date_key,
        end_date_key,
    )
    return {int(r[0]): float(r[1]) for r in cur.fetchall()}


def fetch_cash_flows_by_date(
    conn: pyodbc.Connection,
    portfolio_key: int,
    start_date_key: int | None,
    end_date_key: int | None,
) -> dict[int, float]:
    cur = conn.cursor()
    cur.execute(
        """
SELECT
    TradeDateKey,
    SUM(
        CASE
            WHEN Side = 'BUY' THEN -((Quantity * Price) + FeeAmount)
            ELSE ((Quantity * Price) - FeeAmount)
        END
    ) AS NetCashFlow
FROM dbo.FactTrades
WHERE PortfolioKey = ?
  AND (? IS NULL OR TradeDateKey >= ?)
  AND (? IS NULL OR TradeDateKey <= ?)
GROUP BY TradeDateKey
ORDER BY TradeDateKey
""",
        portfolio_key,
        start_date_key,
        start_date_key,
        end_date_key,
        end_date_key,
    )
    return {int(r[0]): float(r[1]) for r in cur.fetchall()}


def compute_daily_performance(
    date_keys: list[int],
    market_values: dict[int, float],
    cash_flows: dict[int, float],
    initial_nav: float,
) -> list[DailyPerformance]:
    cash_balance = float(initial_nav)
    previous_nav = float(initial_nav)

    results: list[DailyPerformance] = []
    for date_key in date_keys:
        cash_balance += cash_flows.get(date_key, 0.0)
        nav = cash_balance + market_values.get(date_key, 0.0)
        daily_pnl = nav - previous_nav
        cum_pnl = nav - initial_nav
        return_pct = daily_pnl / previous_nav if abs(previous_nav) > 1e-12 else 0.0
        contribution_pct = return_pct

        results.append(
            DailyPerformance(
                date_key=date_key,
                nav=float(nav),
                daily_pnl=float(daily_pnl),
                cum_pnl=float(cum_pnl),
                return_pct=float(return_pct),
                contribution_pct=float(contribution_pct),
            )
        )
        previous_nav = nav

    return results


def compute_daily_risk(perf_rows: list[DailyPerformance]) -> list[DailyRisk]:
    results: list[DailyRisk] = []
    drawdown_min = 0.0
    peak = 0.0
    returns_series: list[float] = []

    for idx, row in enumerate(perf_rows):
        ret = row.return_pct if idx > 0 else 0.0
        returns_series.append(ret)
        window = returns_series[max(0, len(returns_series) - 20) :]

        if len(window) >= 2:
            volatility20d = statistics.stdev(window) * math.sqrt(252.0)
            std_ret = statistics.stdev(window)
            mean_ret = statistics.fmean(window)
            sharpe = (mean_ret / std_ret) * math.sqrt(252.0) if std_ret > 0 else 0.0
        else:
            volatility20d = 0.0
            sharpe = 0.0

        peak = max(peak, row.nav)
        if peak > 0:
            current_drawdown = (row.nav / peak) - 1.0
            drawdown_min = min(drawdown_min, current_drawdown)

        var95_return = percentile(window, 0.05) if window else 0.0
        var95 = min(0.0, var95_return * row.nav)

        results.append(
            DailyRisk(
                date_key=row.date_key,
                volatility20d=float(volatility20d),
                max_drawdown=float(drawdown_min),
                var95=float(var95),
                beta=None,
                sharpe_ratio=float(sharpe),
            )
        )

    return results


def filter_rows_by_date_range(
    rows: list[RowT],
    start_date_key: int | None,
    end_date_key: int | None,
) -> list[RowT]:
    def include(date_key: int) -> bool:
        if start_date_key is not None and date_key < start_date_key:
            return False
        if end_date_key is not None and date_key > end_date_key:
            return False
        return True

    return [row for row in rows if include(int(getattr(row, "date_key")))]


def purge_target_tables(
    conn: pyodbc.Connection,
    portfolio_key: int,
    start_date_key: int,
    end_date_key: int,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
DELETE FROM dbo.PortfolioPnLDaily
WHERE PortfolioKey = ?
  AND DateKey >= ?
  AND DateKey <= ?
""",
        portfolio_key,
        start_date_key,
        end_date_key,
    )
    cur.execute(
        """
DELETE FROM dbo.RiskMetricsDaily
WHERE PortfolioKey = ?
  AND DateKey >= ?
  AND DateKey <= ?
""",
        portfolio_key,
        start_date_key,
        end_date_key,
    )
    conn.commit()


def insert_metrics(
    conn: pyodbc.Connection,
    portfolio_key: int,
    perf_rows: list[DailyPerformance],
    risk_rows: list[DailyRisk],
) -> None:
    cur = conn.cursor()

    if perf_rows:
        cur.fast_executemany = True
        cur.executemany(
            """
INSERT INTO dbo.PortfolioPnLDaily (
    DateKey, PortfolioKey, DailyPnL, CumPnL, Nav, ReturnPct, ContributionPct
) VALUES (?, ?, ?, ?, ?, ?, ?)
""",
            [
                (
                    row.date_key,
                    portfolio_key,
                    row.daily_pnl,
                    row.cum_pnl,
                    row.nav,
                    row.return_pct,
                    row.contribution_pct,
                )
                for row in perf_rows
            ],
        )

    if risk_rows:
        cur.fast_executemany = True
        cur.executemany(
            """
INSERT INTO dbo.RiskMetricsDaily (
    DateKey, PortfolioKey, Volatility20d, MaxDrawdown, VaR95, Beta, SharpeRatio
) VALUES (?, ?, ?, ?, ?, ?, ?)
""",
            [
                (
                    row.date_key,
                    portfolio_key,
                    row.volatility20d,
                    row.max_drawdown,
                    row.var95,
                    row.beta,
                    row.sharpe_ratio,
                )
                for row in risk_rows
            ],
        )

    conn.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute PortfolioPnLDaily and RiskMetricsDaily")
    parser.add_argument("--portfolio-code", default="MAIN", help="Portfolio code from dbo.DimPortfolio")
    parser.add_argument("--initial-nav", type=float, default=100000.0, help="Starting NAV used for cash ledger")
    parser.add_argument("--start-date", default=None, help="Optional filter start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="Optional filter end date (YYYY-MM-DD)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")

    start_date_key = date_to_key(args.start_date)
    end_date_key = date_to_key(args.end_date)

    if start_date_key and end_date_key and start_date_key > end_date_key:
        raise RuntimeError("start-date must be <= end-date")

    with db_connect() as conn:
        portfolio_key = resolve_portfolio_key(conn, args.portfolio_code)
        date_keys = fetch_all_dates(conn, portfolio_key, start_date_key, end_date_key)
        if not date_keys:
            print("No source rows found in FactTrades/PortfolioPositionsDaily for selected filters.")
            return

        ensure_no_missing_prices(conn, portfolio_key, start_date_key, end_date_key)
        market_values = fetch_market_values_by_date(conn, portfolio_key, start_date_key, end_date_key)
        cash_flows = fetch_cash_flows_by_date(conn, portfolio_key, start_date_key, end_date_key)

        perf_all = compute_daily_performance(
            date_keys=date_keys,
            market_values=market_values,
            cash_flows=cash_flows,
            initial_nav=args.initial_nav,
        )
        risk_all = compute_daily_risk(perf_all)

        perf_rows = filter_rows_by_date_range(perf_all, start_date_key, end_date_key)
        risk_rows = filter_rows_by_date_range(risk_all, start_date_key, end_date_key)

        if not perf_rows:
            print("No rows to write after filtering.")
            return

        write_start = perf_rows[0].date_key
        write_end = perf_rows[-1].date_key
        purge_target_tables(conn, portfolio_key, write_start, write_end)
        insert_metrics(conn, portfolio_key, perf_rows, risk_rows)

    print(
        f"Performance & Risk complete: portfolio={args.portfolio_code} "
        f"rows={len(perf_rows)} date_range={write_start}-{write_end}"
    )
    print("Stored outputs in dbo.PortfolioPnLDaily and dbo.RiskMetricsDaily")


if __name__ == "__main__":
    main()

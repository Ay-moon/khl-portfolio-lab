from __future__ import annotations

import pyodbc

from context_schema import (
    ContextPack,
    LatestRecommendationLine,
    PortfolioHeadline,
    PositionLine,
)


def _to_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _resolve_effective_date_key(
    conn: pyodbc.Connection,
    portfolio_code: str,
    date_key: int | None,
) -> int:
    cur = conn.cursor()
    if date_key is not None:
        return int(date_key)

    cur.execute(
        """
SELECT MAX(DateKey)
FROM dbo.vw_PortfolioDashboardDaily
WHERE PortfolioCode = ?
""",
        portfolio_code,
    )
    row = cur.fetchone()
    if row and row[0] is not None:
        return int(row[0])

    cur.execute(
        """
SELECT MAX(DateKey)
FROM dbo.vw_PositionSnapshot
WHERE PortfolioCode = ?
""",
        portfolio_code,
    )
    row = cur.fetchone()
    if row and row[0] is not None:
        return int(row[0])

    raise RuntimeError(f"No data available for portfolio code: {portfolio_code}")


def fetch_context_pack(
    conn: pyodbc.Connection,
    portfolio_code: str,
    date_key: int | None = None,
    top_positions: int = 10,
    top_recommendations: int = 10,
) -> ContextPack:
    effective_date_key = _resolve_effective_date_key(conn, portfolio_code, date_key)
    cur = conn.cursor()

    cur.execute(
        """
SELECT TOP 1
    DateKey,
    CONVERT(VARCHAR(10), FullDate, 120) AS FullDate,
    Nav,
    DailyPnL,
    CumPnL,
    ReturnPct,
    Volatility20d,
    MaxDrawdown,
    VaR95,
    SharpeRatio
FROM dbo.vw_PortfolioDashboardDaily
WHERE PortfolioCode = ?
  AND DateKey = ?
ORDER BY DateKey DESC
""",
        portfolio_code,
        effective_date_key,
    )
    row = cur.fetchone()

    if row:
        headline = PortfolioHeadline(
            date_key=int(row[0]),
            full_date=str(row[1]) if row[1] is not None else None,
            nav=_to_float(row[2]),
            daily_pnl=_to_float(row[3]),
            cum_pnl=_to_float(row[4]),
            return_pct=_to_float(row[5]),
            volatility20d=_to_float(row[6]),
            max_drawdown=_to_float(row[7]),
            var95=_to_float(row[8]),
            sharpe_ratio=_to_float(row[9]),
        )
    else:
        headline = PortfolioHeadline(
            date_key=effective_date_key,
            full_date=None,
            nav=0.0,
            daily_pnl=0.0,
            cum_pnl=0.0,
            return_pct=0.0,
            volatility20d=0.0,
            max_drawdown=0.0,
            var95=0.0,
            sharpe_ratio=0.0,
        )

    cur.execute(
        """
SELECT TOP (?)
    Ticker,
    SecurityName,
    Quantity,
    MarketValue,
    UnrealizedPnL,
    WeightPct
FROM dbo.vw_PositionSnapshot
WHERE PortfolioCode = ?
  AND DateKey = ?
ORDER BY MarketValue DESC, Ticker
""",
        top_positions,
        portfolio_code,
        effective_date_key,
    )
    positions = [
        PositionLine(
            ticker=str(r[0]),
            security_name=str(r[1]),
            quantity=_to_float(r[2]),
            market_value=_to_float(r[3]),
            unrealized_pnl=_to_float(r[4]),
            weight_pct=_to_float(r[5]),
        )
        for r in cur.fetchall()
    ]

    cur.execute(
        """
SELECT TOP (?)
    Ticker,
    Action,
    ConfidenceScore,
    Status,
    CONVERT(VARCHAR(19), CreatedAt, 120) AS CreatedAt
FROM dbo.vw_AI_LatestRecommendations
WHERE PortfolioCode = ?
ORDER BY CreatedAt DESC
""",
        top_recommendations,
        portfolio_code,
    )
    latest_recommendations = [
        LatestRecommendationLine(
            ticker=str(r[0]) if r[0] is not None else None,
            action=str(r[1]),
            confidence_score=float(r[2]) if r[2] is not None else None,
            status=str(r[3]),
            created_at=str(r[4]) if r[4] is not None else None,
        )
        for r in cur.fetchall()
    ]

    return ContextPack(
        portfolio_code=portfolio_code,
        date_key=effective_date_key,
        headline=headline,
        positions=positions,
        latest_recommendations=latest_recommendations,
    )

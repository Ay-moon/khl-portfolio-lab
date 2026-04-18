from __future__ import annotations

from datetime import datetime

import pyodbc

from config import AssistantConfig


def build_connection(config: AssistantConfig) -> pyodbc.Connection:
    parts = [
        f"DRIVER={{{config.sql_driver}}}",
        f"SERVER={config.sql_server}",
        f"DATABASE={config.sql_database}",
        "TrustServerCertificate=yes",
    ]
    if config.sql_auth_mode == "windows":
        parts.append("Trusted_Connection=yes")
    else:
        if not config.sql_user or not config.sql_password:
            raise RuntimeError("SQL_USER and SQL_PASSWORD are required for SQL auth mode")
        parts.append(f"UID={config.sql_user}")
        parts.append(f"PWD={config.sql_password}")
    return pyodbc.connect(";".join(parts))


def parse_date_to_key(raw: str | None) -> int | None:
    if raw is None:
        return None
    dt = datetime.strptime(raw, "%Y-%m-%d")
    return int(dt.strftime("%Y%m%d"))


def resolve_portfolio_key(conn: pyodbc.Connection, portfolio_code: str) -> int:
    cur = conn.cursor()
    cur.execute("SELECT PortfolioKey FROM dbo.DimPortfolio WHERE PortfolioCode = ?", portfolio_code)
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Portfolio code not found in dbo.DimPortfolio: {portfolio_code}")
    return int(row[0])


def resolve_date_key(
    conn: pyodbc.Connection,
    portfolio_code: str,
    preferred_date_key: int | None,
) -> int:
    cur = conn.cursor()

    if preferred_date_key is not None:
        cur.execute(
            """
SELECT 1
FROM dbo.vw_PortfolioDashboardDaily
WHERE PortfolioCode = ?
  AND DateKey = ?
""",
            portfolio_code,
            preferred_date_key,
        )
        if cur.fetchone():
            return preferred_date_key

        cur.execute(
            """
SELECT 1
FROM dbo.vw_PositionSnapshot
WHERE PortfolioCode = ?
  AND DateKey = ?
""",
            portfolio_code,
            preferred_date_key,
        )
        if cur.fetchone():
            return preferred_date_key

        raise RuntimeError(
            f"No data found for portfolio={portfolio_code} and date_key={preferred_date_key}"
        )

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

    raise RuntimeError(
        f"Cannot resolve date for portfolio={portfolio_code}. "
        "Run simulation and performance/risk first."
    )


def ensure_dim_date_exists(conn: pyodbc.Connection, date_key: int) -> None:
    d = datetime.strptime(str(date_key), "%Y%m%d").date()
    cur = conn.cursor()
    cur.execute(
        """
IF NOT EXISTS (SELECT 1 FROM dbo.DimDate WHERE DateKey = ?)
BEGIN
    INSERT INTO dbo.DimDate (
        DateKey, FullDate, CalendarYear, CalendarMonth, CalendarDay,
        MonthName, QuarterNumber, WeekOfYear, IsMonthEnd
    )
    VALUES (
        ?, ?, ?, ?, ?,
        DATENAME(MONTH, ?),
        DATEPART(QUARTER, ?),
        DATEPART(ISO_WEEK, ?),
        CASE WHEN EOMONTH(?) = ? THEN 1 ELSE 0 END
    )
END
""",
        date_key,
        date_key,
        d,
        d.year,
        d.month,
        d.day,
        d,
        d,
        d,
        d,
        d,
    )
    conn.commit()

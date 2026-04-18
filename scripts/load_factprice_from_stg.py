from __future__ import annotations

import argparse
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pyodbc


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class StgPriceRow:
    stg_id: int
    date_key: int
    source_dt: datetime
    canonical_name: str
    produit_type: str
    close_price: float
    volume: int | None
    load_ts: datetime


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


def build_connection(database: str | None = None) -> pyodbc.Connection:
    driver = require_env("SQL_DRIVER")
    server = require_env("SQL_SERVER")
    auth_mode = os.getenv("SQL_AUTH_MODE", "sql").lower().strip()

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database or require_env('SQL_DATABASE')}",
        "TrustServerCertificate=yes",
    ]

    if auth_mode == "windows":
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={require_env('SQL_USER')}")
        parts.append(f"PWD={require_env('SQL_PASSWORD')}")

    return pyodbc.connect(";".join(parts))


def date_key_from_datetime(dt: datetime) -> int:
    return int(dt.strftime("%Y%m%d"))


def parse_decimal_text(raw: str | None) -> float | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None

    value = value.replace("\u00A0", " ")
    value = value.replace("(c)", "").replace("(C)", "")
    value = re.sub(r"[^0-9,.\- ]", "", value)
    value = value.replace(" ", "")
    if not value:
        return None

    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")

    try:
        return float(value)
    except ValueError:
        return None


def parse_volume_text(raw: str | None) -> int | None:
    val = parse_decimal_text(raw)
    if val is None:
        return None
    if val < 0:
        return None
    return int(round(val))


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def canonical_security_name(
    libelle: str | None,
    sous_jacent: str | None,
    ss_jacent: str | None,
    produit: str | None,
    isin: str | None,
) -> str | None:
    candidates = [
        libelle or "",
        ss_jacent or "",
        sous_jacent or "",
        produit or "",
        isin or "",
    ]

    for raw in candidates:
        value = normalize_whitespace(raw)
        if not value:
            continue

        upper = value.upper()
        if upper.startswith("SRD "):
            value = normalize_whitespace(value[4:])
        elif upper.startswith("SRD-"):
            value = normalize_whitespace(value[4:])

        value = value.strip("-_/ ")
        if value:
            return value
    return None


def slugify_ascii(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "", ascii_only).upper()


def make_unique_ticker(
    base_name: str,
    existing_tickers_upper: set[str],
    reserved_tickers_upper: set[str],
    max_len: int = 20,
) -> str:
    base = slugify_ascii(base_name)
    if not base:
        base = "SECURITY"
    base = base[:max_len]
    if not base:
        base = "SECURITY"

    candidate = base
    idx = 2
    while candidate.upper() in existing_tickers_upper or candidate.upper() in reserved_tickers_upper:
        suffix = str(idx)
        prefix_len = max_len - len(suffix)
        candidate = f"{base[:prefix_len]}{suffix}"
        idx += 1
    reserved_tickers_upper.add(candidate.upper())
    return candidate


def ensure_dim_date(conn: pyodbc.Connection, all_dates: list[date]) -> None:
    if not all_dates:
        return

    sql = """
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
"""
    rows = []
    for d in all_dates:
        dk = int(d.strftime("%Y%m%d"))
        rows.append((dk, dk, d, d.year, d.month, d.day, d, d, d, d, d))

    cur = conn.cursor()
    cur.fast_executemany = True
    cur.executemany(sql, rows)
    conn.commit()


def fetch_source_rows(
    conn: pyodbc.Connection,
    source_db: str,
    source_schema: str,
    source_table: str,
    product_type: str,
    start_date: str | None,
    end_date: str | None,
) -> list[StgPriceRow]:
    sql = f"""
SELECT
    stg_id,
    date_extraction,
    isin,
    libelle,
    produit,
    produit_type,
    sous_jacent,
    ss_jacent,
    dernier,
    volume,
    load_ts
FROM [{source_db}].[{source_schema}].[{source_table}]
WHERE UPPER(LTRIM(RTRIM(produit_type))) = UPPER(?)
  AND date_extraction IS NOT NULL
  AND NULLIF(LTRIM(RTRIM(dernier)), '') IS NOT NULL
  AND (? IS NULL OR CAST(date_extraction AS date) >= ?)
  AND (? IS NULL OR CAST(date_extraction AS date) <= ?)
ORDER BY load_ts, stg_id
"""
    cur = conn.cursor()
    cur.execute(sql, product_type, start_date, start_date, end_date, end_date)

    prepared: list[StgPriceRow] = []
    for row in cur.fetchall():
        stg_id = int(row[0])
        dt = row[1]
        if not isinstance(dt, datetime):
            continue

        canonical = canonical_security_name(
            libelle=row[3],
            sous_jacent=row[6],
            ss_jacent=row[7],
            produit=row[4],
            isin=row[2],
        )
        if not canonical:
            continue

        close_price = parse_decimal_text(row[8])
        if close_price is None:
            continue

        volume = parse_volume_text(row[9])
        load_ts = row[10] if isinstance(row[10], datetime) else dt
        prepared.append(
            StgPriceRow(
                stg_id=stg_id,
                date_key=date_key_from_datetime(dt),
                source_dt=dt,
                canonical_name=canonical,
                produit_type=str(row[5]),
                close_price=close_price,
                volume=volume,
                load_ts=load_ts,
            )
        )

    return prepared


def deduplicate_rows(rows: list[StgPriceRow]) -> list[StgPriceRow]:
    latest_by_key: dict[tuple[int, str], StgPriceRow] = {}
    for row in rows:
        key = (row.date_key, row.canonical_name.upper())
        prev = latest_by_key.get(key)
        if prev is None:
            latest_by_key[key] = row
            continue
        prev_sort = (prev.load_ts, prev.stg_id)
        curr_sort = (row.load_ts, row.stg_id)
        if curr_sort >= prev_sort:
            latest_by_key[key] = row
    return list(latest_by_key.values())


def load_existing_securities(conn: pyodbc.Connection) -> list[tuple[int, str, str]]:
    cur = conn.cursor()
    cur.execute("SELECT SecurityKey, Ticker, SecurityName FROM dbo.DimSecurity")
    return [(int(r[0]), str(r[1]), str(r[2])) for r in cur.fetchall()]


def ensure_securities_for_rows(
    conn: pyodbc.Connection,
    rows: list[StgPriceRow],
    default_ccy: str,
) -> tuple[dict[str, int], int]:
    existing = load_existing_securities(conn)
    by_name_upper: dict[str, int] = {}
    by_ticker_upper: dict[str, int] = {}
    existing_tickers_upper: set[str] = set()

    for key, ticker, name in existing:
        by_name_upper[name.upper()] = key
        by_ticker_upper[ticker.upper()] = key
        existing_tickers_upper.add(ticker.upper())

    needed_names_upper = sorted({r.canonical_name.upper() for r in rows})
    missing_names_upper = [
        n for n in needed_names_upper if n not in by_name_upper and n not in by_ticker_upper
    ]

    _PRODUIT_TO_ASSET_CLASS = {
        "ACTION":      "Equity",
        "ETF":         "ETF",
        "OBLIGATION":  "Bond",
        "TRACKER":     "ETF",
        "WARRANT":     "Warrant",
        "CERTIFICAT":  "Certificate",
        "TURBO":       "Structured",
        "OPCVM":       "Fund",
    }

    produit_by_name_upper: dict[str, str] = {
        r.canonical_name.upper(): r.produit_type.upper() for r in rows
    }

    inserted_count = 0
    if missing_names_upper:
        original_name_by_upper = {r.canonical_name.upper(): r.canonical_name for r in rows}
        reserved: set[str] = set()
        insert_payload = []

        for upper_name in missing_names_upper:
            display_name = original_name_by_upper[upper_name]
            ticker = make_unique_ticker(display_name, existing_tickers_upper, reserved, max_len=20)
            produit = produit_by_name_upper.get(upper_name, "")
            asset_class = _PRODUIT_TO_ASSET_CLASS.get(produit, "Unknown")
            insert_payload.append((ticker, display_name, asset_class, default_ccy))

        cur = conn.cursor()
        cur.fast_executemany = True
        cur.executemany(
            """
INSERT INTO dbo.DimSecurity (Ticker, SecurityName, AssetClass, CurrencyCode)
VALUES (?, ?, ?, ?)
""",
            insert_payload,
        )
        conn.commit()
        inserted_count = len(insert_payload)

        existing = load_existing_securities(conn)
        by_name_upper.clear()
        by_ticker_upper.clear()
        for key, ticker, name in existing:
            by_name_upper[name.upper()] = key
            by_ticker_upper[ticker.upper()] = key

    mapping: dict[str, int] = {}
    for row in rows:
        k = row.canonical_name.upper()
        if k in by_name_upper:
            mapping[k] = by_name_upper[k]
        elif k in by_ticker_upper:
            mapping[k] = by_ticker_upper[k]

    unresolved = sorted({r.canonical_name for r in rows if r.canonical_name.upper() not in mapping})
    if unresolved:
        raise RuntimeError(f"Unresolved securities after upsert (sample): {unresolved[:10]}")

    return mapping, inserted_count


def merge_fact_price(
    conn: pyodbc.Connection,
    fact_rows: list[tuple[int, int, float, int | None, str]],
) -> tuple[int, int]:
    if not fact_rows:
        return 0, 0

    cur = conn.cursor()
    cur.execute(
        """
CREATE TABLE #SrcFactPrice(
    DateKey INT NOT NULL,
    SecurityKey INT NOT NULL,
    ClosePrice DECIMAL(19,6) NOT NULL,
    Volume BIGINT NULL,
    SourceSystem NVARCHAR(50) NULL
)
"""
    )

    cur.executemany(
        """
INSERT INTO #SrcFactPrice(DateKey, SecurityKey, ClosePrice, Volume, SourceSystem)
VALUES (?, ?, ?, ?, ?)
""",
        fact_rows,
    )

    cur.execute(
        """
DECLARE @changes TABLE(action NVARCHAR(10) NOT NULL);

MERGE dbo.FactPrice AS tgt
USING #SrcFactPrice AS src
   ON tgt.DateKey = src.DateKey
  AND tgt.SecurityKey = src.SecurityKey
WHEN MATCHED THEN
    UPDATE SET
        tgt.ClosePrice = src.ClosePrice,
        tgt.Volume = src.Volume,
        tgt.SourceSystem = src.SourceSystem
WHEN NOT MATCHED THEN
    INSERT (DateKey, SecurityKey, ClosePrice, Volume, SourceSystem)
    VALUES (src.DateKey, src.SecurityKey, src.ClosePrice, src.Volume, src.SourceSystem)
OUTPUT $action INTO @changes(action);

SELECT
    SUM(CASE WHEN action = 'INSERT' THEN 1 ELSE 0 END) AS inserted_count,
    SUM(CASE WHEN action = 'UPDATE' THEN 1 ELSE 0 END) AS updated_count
FROM @changes;
"""
    )

    while cur.description is None:
        has_next = cur.nextset()
        if not has_next:
            raise RuntimeError("MERGE completed but no result set returned for inserted/updated counts.")

    row = cur.fetchone()
    inserted = int(row[0] or 0)
    updated = int(row[1] or 0)
    conn.commit()
    return inserted, updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load real market prices from stg_bourso_price_history into dbo.FactPrice"
    )
    parser.add_argument("--source-db", default=os.getenv("SQL_DATABASE_STG", "KHLWorldInvest"))
    parser.add_argument("--source-schema", default=os.getenv("SQL_SCHEMA_STG", "stg"))
    parser.add_argument("--source-table", default="stg_bourso_price_history")
    parser.add_argument("--product-type", default="ACTION", help="Source product type filter")
    parser.add_argument("--start-date", default=None, help="Optional date filter start (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="Optional date filter end (YYYY-MM-DD)")
    parser.add_argument("--default-ccy", default="EUR", help="Currency used for newly created DimSecurity")
    parser.add_argument("--dry-run", action="store_true", help="Read/prepare but do not write")
    return parser.parse_args()


def validate_date(raw: str | None) -> str | None:
    if raw is None:
        return None
    datetime.strptime(raw, "%Y-%m-%d")
    return raw


def main() -> None:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")

    start_date = validate_date(args.start_date)
    end_date = validate_date(args.end_date)
    if start_date and end_date and start_date > end_date:
        raise RuntimeError("start-date must be <= end-date")

    source_system = f"{args.source_db}.{args.source_schema}.{args.source_table}"

    with build_connection() as conn:
        raw_rows = fetch_source_rows(
            conn=conn,
            source_db=args.source_db,
            source_schema=args.source_schema,
            source_table=args.source_table,
            product_type=args.product_type,
            start_date=start_date,
            end_date=end_date,
        )
        dedup_rows = deduplicate_rows(raw_rows)

        if not dedup_rows:
            print("No eligible rows from source (after parsing/deduplication).")
            return

        unique_dates = sorted({datetime.strptime(str(r.date_key), "%Y%m%d").date() for r in dedup_rows})
        unique_names = sorted({r.canonical_name for r in dedup_rows})

        print(
            f"Prepared source rows: raw={len(raw_rows)} dedup={len(dedup_rows)} "
            f"unique_dates={len(unique_dates)} unique_securities={len(unique_names)}"
        )

        if args.dry_run:
            print("Dry-run enabled: no DB writes.")
            return

        ensure_dim_date(conn, unique_dates)
        security_map, inserted_securities = ensure_securities_for_rows(
            conn=conn,
            rows=dedup_rows,
            default_ccy=args.default_ccy,
        )

        fact_rows: list[tuple[int, int, float, int | None, str]] = []
        for row in dedup_rows:
            security_key = security_map[row.canonical_name.upper()]
            fact_rows.append(
                (
                    row.date_key,
                    security_key,
                    round(row.close_price, 6),
                    row.volume,
                    source_system[:50],
                )
            )

        inserted_fact, updated_fact = merge_fact_price(conn, fact_rows)

    print(
        f"FactPrice load complete: inserted={inserted_fact} updated={updated_fact} "
        f"new_securities={inserted_securities} source={source_system}"
    )


if __name__ == "__main__":
    main()

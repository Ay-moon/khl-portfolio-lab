import os
import re
from pathlib import Path

import pyodbc


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def build_connection(database: str | None = None, autocommit: bool = False):
    driver = require("SQL_DRIVER")
    server = require("SQL_SERVER")
    auth_mode = os.getenv("SQL_AUTH_MODE", "sql").strip().lower()

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database or require('SQL_DATABASE')}",
        "TrustServerCertificate=yes",
    ]

    if auth_mode == "windows":
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={require('SQL_USER')}")
        parts.append(f"PWD={require('SQL_PASSWORD')}")

    conn_str = ";".join(parts)
    return pyodbc.connect(conn_str, autocommit=autocommit)


def can_connect(database: str) -> bool:
    try:
        with build_connection(database=database):
            return True
    except pyodbc.Error:
        return False


def resolve_target_database() -> tuple[str, list[str]]:
    logs: list[str] = []
    primary_db = require("SQL_DATABASE")

    if can_connect(primary_db):
        logs.append(f"Using database: {primary_db}")
        return primary_db, logs

    logs.append(f"Database {primary_db} not reachable yet; trying to create it.")
    try:
        with build_connection(database="master", autocommit=True) as conn:
            cursor = conn.cursor()
            sql = f"IF DB_ID(N'{primary_db}') IS NULL CREATE DATABASE [{primary_db}];"
            cursor.execute(sql)
        if can_connect(primary_db):
            logs.append(f"Database created: {primary_db}")
            return primary_db, logs
    except pyodbc.Error as exc:
        logs.append(f"Create database skipped/failed: {exc}")

    raise RuntimeError(
        f"Unable to connect to required database '{primary_db}'. "
        "Check SQL_DATABASE value and permissions (CREATE DATABASE / connect rights)."
    )


def ensure_seed_table(database: str) -> None:
    schema = os.getenv("SQL_SCHEMA", "dbo")
    table_sql = f"""
IF SCHEMA_ID('{schema}') IS NULL EXEC('CREATE SCHEMA [{schema}]');
IF OBJECT_ID('{schema}.SeedHealthcheck', 'U') IS NULL
BEGIN
    CREATE TABLE [{schema}].[SeedHealthcheck](
        Id INT IDENTITY(1,1) PRIMARY KEY,
        Label NVARCHAR(100) NOT NULL,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
INSERT INTO [{schema}].[SeedHealthcheck](Label) VALUES ('bootstrap-seed');
"""

    with build_connection(database=database) as conn:
        cursor = conn.cursor()
        cursor.execute(table_sql)
        conn.commit()


def split_batches(sql_text: str) -> list[str]:
    # Split SQL scripts on batch separators "GO" written alone on a line.
    chunks = re.split(r"(?im)^[ \t]*GO[ \t]*$", sql_text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def run_sql_file(conn: pyodbc.Connection, path: Path) -> None:
    sql_text = path.read_text(encoding="utf-8")
    batches = split_batches(sql_text)
    cursor = conn.cursor()
    for batch in batches:
        cursor.execute(batch)
    conn.commit()


def apply_sql_assets(database: str, repo_root: Path) -> None:
    ddl_dir = repo_root / "data-platform" / "sql" / "ddl"
    dml_dir = repo_root / "data-platform" / "sql" / "dml"

    with build_connection(database=database) as conn:
        for sql_file in sorted(ddl_dir.glob("*.sql")):
            print(f"Applying DDL: {sql_file.name}")
            run_sql_file(conn, sql_file)

        for sql_file in sorted(dml_dir.glob("*.sql")):
            print(f"Applying DML: {sql_file.name}")
            run_sql_file(conn, sql_file)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    database, logs = resolve_target_database()
    for line in logs:
        print(line)

    apply_sql_assets(database, repo_root)
    ensure_seed_table(database)
    print(
        "Seed completed: database reachable, schema/table ready, sample row inserted."
    )


if __name__ == "__main__":
    main()

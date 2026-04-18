from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AssistantConfig:
    provider: str
    openai_api_key: str | None
    sql_driver: str
    sql_server: str
    sql_database: str
    sql_auth_mode: str
    sql_user: str | None
    sql_password: str | None


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def load_config(dotenv_path: Path | None = None) -> AssistantConfig:
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(dotenv_path or (repo_root / ".env"))

    provider = os.getenv("AI_PROVIDER", "mock").strip().lower()
    if provider not in {"mock", "openai"}:
        raise RuntimeError("AI_PROVIDER must be one of: mock, openai")

    openai_api_key = os.getenv("OPENAI_API_KEY") or None
    if provider == "openai" and not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when AI_PROVIDER=openai")

    sql_driver = _require_env("SQL_DRIVER")
    sql_server = _require_env("SQL_SERVER")
    sql_database = _require_env("SQL_DATABASE")
    sql_auth_mode = os.getenv("SQL_AUTH_MODE", "sql").strip().lower()

    sql_user: str | None = None
    sql_password: str | None = None
    if sql_auth_mode != "windows":
        sql_user = _require_env("SQL_USER")
        sql_password = _require_env("SQL_PASSWORD")

    return AssistantConfig(
        provider=provider,
        openai_api_key=openai_api_key,
        sql_driver=sql_driver,
        sql_server=sql_server,
        sql_database=sql_database,
        sql_auth_mode=sql_auth_mode,
        sql_user=sql_user,
        sql_password=sql_password,
    )

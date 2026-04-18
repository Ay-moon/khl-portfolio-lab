from __future__ import annotations

import json
from typing import Any

import pyodbc

from schemas import DailyBriefingOutput, RecommendationsOutput, WhatIfOutput


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def resolve_security_map(conn: pyodbc.Connection, tickers: list[str]) -> dict[str, int]:
    cleaned = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    if not cleaned:
        return {}

    placeholders = ",".join("?" for _ in cleaned)
    sql = f"SELECT Ticker, SecurityKey FROM dbo.DimSecurity WHERE UPPER(Ticker) IN ({placeholders})"
    cur = conn.cursor()
    cur.execute(sql, cleaned)
    rows = cur.fetchall()
    return {str(r[0]).upper(): int(r[1]) for r in rows}


def write_audit_log(
    conn: pyodbc.Connection,
    event_type: str,
    component: str,
    status: str,
    detail: str,
    input_hash: str | None = None,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
INSERT INTO dbo.AI_AuditLog (EventType, Component, InputHash, Status, Detail)
VALUES (?, ?, ?, ?, ?)
""",
        event_type,
        component,
        input_hash,
        status,
        detail,
    )
    conn.commit()


def write_daily_briefing(
    conn: pyodbc.Connection,
    date_key: int,
    portfolio_key: int | None,
    model_name: str,
    prompt_version: str,
    output: DailyBriefingOutput,
) -> int:
    output_json = _json_dump(output.to_dict())
    assumptions_text = "\n".join(output.assumptions)

    cur = conn.cursor()
    cur.execute(
        """
INSERT INTO dbo.AI_DailyBriefing (
    DateKey, PortfolioKey, ModelName, PromptVersion, OutputJson, Summary, Assumptions
)
VALUES (?, ?, ?, ?, ?, ?, ?)
""",
        date_key,
        portfolio_key,
        model_name,
        prompt_version,
        output_json,
        output.summary,
        assumptions_text,
    )
    cur.execute("SELECT CAST(SCOPE_IDENTITY() AS BIGINT)")
    row = cur.fetchone()
    conn.commit()
    return int(row[0])


def write_recommendations(
    conn: pyodbc.Connection,
    date_key: int,
    portfolio_key: int | None,
    model_name: str,
    prompt_version: str,
    output: RecommendationsOutput,
    status: str = "proposed",
) -> int:
    tickers = [x.ticker for x in output.recommendations]
    security_map = resolve_security_map(conn, tickers)

    rows: list[tuple] = []
    for item in output.recommendations:
        payload = item.__dict__.copy()
        payload["model_name"] = model_name
        payload["prompt_version"] = prompt_version
        rows.append(
            (
                date_key,
                portfolio_key,
                security_map.get(item.ticker.strip().upper()),
                item.normalized_action(),
                float(item.confidence_score),
                item.reasoning,
                item.constraints_check,
                _json_dump(payload),
                status,
            )
        )

    if not rows:
        return 0

    cur = conn.cursor()
    cur.fast_executemany = True
    cur.executemany(
        """
INSERT INTO dbo.AI_Recommendations (
    DateKey, PortfolioKey, SecurityKey, Action, ConfidenceScore,
    Reasoning, ConstraintsCheck, OutputJson, Status
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""",
        rows,
    )
    conn.commit()
    return len(rows)


def write_what_if(
    conn: pyodbc.Connection,
    date_key: int,
    portfolio_key: int | None,
    output: WhatIfOutput,
) -> int:
    input_json = _json_dump({"scenario_name": output.scenario_name})
    result_json = _json_dump(
        {
            "expected_volatility_delta": output.expected_volatility_delta,
            "expected_return_delta": output.expected_return_delta,
        }
    )

    cur = conn.cursor()
    cur.execute(
        """
INSERT INTO dbo.AI_WhatIf (
    DateKey, PortfolioKey, ScenarioName, InputJson, ResultJson, Narrative
)
VALUES (?, ?, ?, ?, ?, ?)
""",
        date_key,
        portfolio_key,
        output.scenario_name,
        input_json,
        result_json,
        output.narrative,
    )
    cur.execute("SELECT CAST(SCOPE_IDENTITY() AS BIGINT)")
    row = cur.fetchone()
    conn.commit()
    return int(row[0])

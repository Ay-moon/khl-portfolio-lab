from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
AI_ROOT = CURRENT_DIR.parent
RAG_DIR = AI_ROOT / "rag"
OUTPUTS_DIR = AI_ROOT / "outputs"
RULES_DIR = AI_ROOT / "rules"

for path in (CURRENT_DIR, RAG_DIR, OUTPUTS_DIR, RULES_DIR):
    p = str(path)
    if p not in sys.path:
        sys.path.append(p)

from config import load_config  # noqa: E402
from constraints import (  # noqa: E402
    check_daily_briefing_constraints,
    check_recommendations_constraints,
    check_what_if_constraints,
)
from db import (  # noqa: E402
    build_connection,
    ensure_dim_date_exists,
    parse_date_to_key,
    resolve_date_key,
    resolve_portfolio_key,
)
from postcheck import (  # noqa: E402
    postcheck_daily_briefing,
    postcheck_recommendations,
    postcheck_what_if,
    raise_if_issues,
)
from retriever import fetch_context_pack  # noqa: E402
from schemas import (  # noqa: E402
    DailyBriefingOutput,
    RecommendationItem,
    RecommendationsOutput,
    WhatIfOutput,
)
from writers import (  # noqa: E402
    write_audit_log,
    write_daily_briefing,
    write_recommendations,
    write_what_if,
)


def build_daily_briefing_mock(context) -> DailyBriefingOutput:
    h = context.headline
    if h.return_pct > 0.002:
        regime = "constructive"
    elif h.return_pct < -0.002:
        regime = "defensive"
    else:
        regime = "neutral"

    focus = [p.ticker for p in context.positions[:3]]
    summary = (
        f"Portfolio {context.portfolio_code} on {h.date_key}: NAV={h.nav:.2f}, "
        f"daily_pnl={h.daily_pnl:.2f}, drawdown={h.max_drawdown:.4f}. "
        f"Current market regime is {regime}."
    )
    assumptions = [
        "No auto-trading is executed by this assistant.",
        "Liquidity and transaction costs remain within usual historical bands.",
    ]
    return DailyBriefingOutput(
        market_regime=regime,
        summary=summary,
        assumptions=assumptions,
        focus_tickers=focus,
        confidence=0.72,
    )


def build_recommendations_mock(context) -> RecommendationsOutput:
    recs: list[RecommendationItem] = []
    for pos in context.positions[:5]:
        weight = float(pos.weight_pct)
        if weight > 0.40:
            action = "REDUCE"
            target_weight = 0.35
            confidence = 0.68
            reasoning = (
                f"{pos.ticker} has high concentration ({weight:.2%}). "
                "A moderate reduction can improve diversification and drawdown profile."
            )
        elif pos.unrealized_pnl > 0 and weight < 0.25:
            action = "INCREASE"
            target_weight = min(0.35, weight + 0.03)
            confidence = 0.64
            reasoning = (
                f"{pos.ticker} shows positive unrealized momentum with controlled weight "
                f"({weight:.2%}), supporting a small incremental increase."
            )
        else:
            action = "HOLD"
            target_weight = weight
            confidence = 0.60
            reasoning = (
                f"{pos.ticker} is currently close to target exposure with no strong "
                "rebalancing signal."
            )

        recs.append(
            RecommendationItem(
                ticker=pos.ticker,
                action=action,
                confidence_score=confidence,
                reasoning=reasoning,
                constraints_check="No concentration/risk hard-limit breach detected in MVP rules.",
                target_weight=round(float(target_weight), 4),
                horizon_days=20,
            )
        )

    if not recs:
        recs = [
            RecommendationItem(
                ticker="SPY",
                action="HOLD",
                confidence_score=0.55,
                reasoning="No position-level signal available; keep neutral allocation until new data arrives.",
                constraints_check="No hard constraint breach.",
                target_weight=0.20,
                horizon_days=20,
            )
        ]

    return RecommendationsOutput(
        recommendations=recs,
        global_summary="Recommendations are risk-aware and remain decision-support only.",
    )


def build_what_if_mock(context, scenario_name: str | None) -> WhatIfOutput:
    top_weight = max((float(p.weight_pct) for p in context.positions), default=0.0)
    scenario = scenario_name or "Reduce largest line by 3% and distribute to top 2 diversifiers"

    expected_vol_delta = round(-0.015 * top_weight, 6)
    expected_ret_delta = round(0.004 * (0.30 - top_weight), 6)
    narrative = (
        f"Scenario '{scenario}' is expected to slightly reduce concentration risk. "
        f"Estimated volatility delta={expected_vol_delta:.6f}, "
        f"estimated return delta={expected_ret_delta:.6f}."
    )
    return WhatIfOutput(
        scenario_name=scenario,
        narrative=narrative,
        expected_volatility_delta=expected_vol_delta,
        expected_return_delta=expected_ret_delta,
    )


def _emit_preview(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI assistant MVP runner (mock-first)")
    parser.add_argument(
        "command",
        choices=["daily-briefing", "recommendations", "what-if"],
        help="Type of AI output to generate",
    )
    parser.add_argument("--portfolio-code", default="MAIN", help="PortfolioCode from dbo.DimPortfolio")
    parser.add_argument("--date", default=None, help="Optional date (YYYY-MM-DD)")
    parser.add_argument("--provider", default="mock", choices=["mock", "openai"], help="AI provider")
    parser.add_argument("--model-name", default="mock-gpt", help="Model name stored in AI tables")
    parser.add_argument("--prompt-version", default="v1", help="Prompt version stored in AI tables")
    parser.add_argument("--scenario-name", default=None, help="Scenario name for what-if command")
    parser.add_argument("--dry-run", action="store_true", help="Preview output without DB writes")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config()
    cfg.provider = args.provider

    if cfg.provider != "mock":
        raise RuntimeError("Only provider=mock is implemented in this MVP runtime.")

    preferred_date_key = parse_date_to_key(args.date)

    with build_connection(cfg) as conn:
        portfolio_key = resolve_portfolio_key(conn, args.portfolio_code)
        date_key = resolve_date_key(conn, args.portfolio_code, preferred_date_key)
        context = fetch_context_pack(conn, args.portfolio_code, date_key=date_key)

        ensure_dim_date_exists(conn, context.date_key)

        if args.command == "daily-briefing":
            out = build_daily_briefing_mock(context)
            out.validate()
            issues = check_daily_briefing_constraints(out) + postcheck_daily_briefing(out)
            raise_if_issues(issues, "daily-briefing")

            if args.dry_run:
                _emit_preview(out.to_dict())
                print("Dry-run: no SQL write performed.")
            else:
                briefing_id = write_daily_briefing(
                    conn,
                    date_key=context.date_key,
                    portfolio_key=portfolio_key,
                    model_name=args.model_name,
                    prompt_version=args.prompt_version,
                    output=out,
                )
                write_audit_log(
                    conn,
                    event_type="daily-briefing",
                    component="ai-assistant/app/main.py",
                    status="success",
                    detail=f"Daily briefing written: BriefingId={briefing_id}",
                )
                print(f"Daily briefing written: BriefingId={briefing_id}")

        elif args.command == "recommendations":
            out = build_recommendations_mock(context)
            out.validate()
            issues = check_recommendations_constraints(out) + postcheck_recommendations(out)
            raise_if_issues(issues, "recommendations")

            if args.dry_run:
                _emit_preview(out.to_dict())
                print("Dry-run: no SQL write performed.")
            else:
                row_count = write_recommendations(
                    conn,
                    date_key=context.date_key,
                    portfolio_key=portfolio_key,
                    model_name=args.model_name,
                    prompt_version=args.prompt_version,
                    output=out,
                    status="proposed",
                )
                write_audit_log(
                    conn,
                    event_type="recommendations",
                    component="ai-assistant/app/main.py",
                    status="success",
                    detail=f"Recommendations written: rows={row_count}",
                )
                print(f"Recommendations written: rows={row_count}")

        else:
            out = build_what_if_mock(context, args.scenario_name)
            out.validate()
            issues = check_what_if_constraints(out) + postcheck_what_if(out)
            raise_if_issues(issues, "what-if")

            if args.dry_run:
                _emit_preview(out.to_dict())
                print("Dry-run: no SQL write performed.")
            else:
                whatif_id = write_what_if(
                    conn,
                    date_key=context.date_key,
                    portfolio_key=portfolio_key,
                    output=out,
                )
                write_audit_log(
                    conn,
                    event_type="what-if",
                    component="ai-assistant/app/main.py",
                    status="success",
                    detail=f"What-if written: WhatIfId={whatif_id}",
                )
                print(f"What-if written: WhatIfId={whatif_id}")


if __name__ == "__main__":
    main()

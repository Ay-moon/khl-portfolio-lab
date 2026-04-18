from __future__ import annotations

from schemas import DailyBriefingOutput, RecommendationsOutput, WhatIfOutput


def raise_if_issues(issues: list[str], component: str) -> None:
    if not issues:
        return
    msg = f"{component} postcheck failed: " + "; ".join(issues)
    raise RuntimeError(msg)


def postcheck_daily_briefing(output: DailyBriefingOutput) -> list[str]:
    issues: list[str] = []
    if len(output.assumptions) < 1:
        issues.append("At least one assumption is required.")
    if len(output.summary.strip()) < 20:
        issues.append("Summary is too short (<20 chars).")
    return issues


def postcheck_recommendations(output: RecommendationsOutput) -> list[str]:
    issues: list[str] = []
    seen: set[str] = set()
    for rec in output.recommendations:
        t = rec.ticker.strip().upper()
        if t in seen:
            issues.append(f"Duplicate ticker in recommendations: {t}")
        seen.add(t)
        if rec.normalized_action() != "HOLD" and len(rec.reasoning.strip()) < 30:
            issues.append(f"{t}: reasoning too short for non-HOLD action.")
    return issues


def postcheck_what_if(output: WhatIfOutput) -> list[str]:
    issues: list[str] = []
    if len(output.narrative.strip()) < 20:
        issues.append("What-if narrative is too short (<20 chars).")
    return issues

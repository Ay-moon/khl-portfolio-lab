from __future__ import annotations

from schemas import DailyBriefingOutput, RecommendationsOutput, WhatIfOutput


_BANNED_EXECUTION_PHRASES = {
    "execute immediately",
    "auto trade",
    "place order now",
    "send order now",
}


def _has_banned_phrase(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in _BANNED_EXECUTION_PHRASES)


def check_daily_briefing_constraints(output: DailyBriefingOutput) -> list[str]:
    issues: list[str] = []
    if output.confidence > 0.95:
        issues.append("Confidence too high for decision-support context (>0.95).")
    if len(output.focus_tickers) > 8:
        issues.append("Too many focus tickers (>8).")
    if _has_banned_phrase(output.summary):
        issues.append("Summary contains forbidden auto-execution language.")
    return issues


def check_recommendations_constraints(
    output: RecommendationsOutput,
    max_items: int = 10,
    max_target_weight: float = 0.40,
) -> list[str]:
    issues: list[str] = []
    if len(output.recommendations) > max_items:
        issues.append(f"Too many recommendations ({len(output.recommendations)} > {max_items}).")

    for rec in output.recommendations:
        if _has_banned_phrase(rec.reasoning):
            issues.append(f"{rec.ticker}: forbidden auto-execution wording.")
        if rec.target_weight is not None and rec.target_weight > max_target_weight:
            issues.append(
                f"{rec.ticker}: target_weight={rec.target_weight:.3f} exceeds limit {max_target_weight:.3f}."
            )
    return issues


def check_what_if_constraints(output: WhatIfOutput) -> list[str]:
    issues: list[str] = []
    if _has_banned_phrase(output.narrative):
        issues.append("What-if narrative contains forbidden auto-execution language.")
    return issues

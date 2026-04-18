from __future__ import annotations

import sys
import unittest
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = AI_DIR / "outputs"
RULES_DIR = AI_DIR / "rules"
for p in (OUTPUTS_DIR, RULES_DIR):
    s = str(p)
    if s not in sys.path:
        sys.path.append(s)

from constraints import check_recommendations_constraints  # noqa: E402
from postcheck import postcheck_recommendations  # noqa: E402
from schemas import RecommendationItem, RecommendationsOutput  # noqa: E402


class SchemasAndRulesTests(unittest.TestCase):
    def test_recommendations_schema_validate_ok(self) -> None:
        output = RecommendationsOutput(
            recommendations=[
                RecommendationItem(
                    ticker="AAPL",
                    action="BUY",
                    confidence_score=0.7,
                    reasoning="Signal quality is positive and exposure remains within limits.",
                    constraints_check="No hard limits breached.",
                    target_weight=0.25,
                    horizon_days=20,
                )
            ],
            global_summary="Single recommendation for smoke test.",
        )
        output.validate()

    def test_recommendations_constraint_rejects_high_target_weight(self) -> None:
        output = RecommendationsOutput(
            recommendations=[
                RecommendationItem(
                    ticker="MSFT",
                    action="BUY",
                    confidence_score=0.66,
                    reasoning="Valid detailed reasoning above minimum threshold for review.",
                    constraints_check="No hard limits breached.",
                    target_weight=0.55,
                    horizon_days=20,
                )
            ],
            global_summary="Test high target weight.",
        )
        output.validate()
        issues = check_recommendations_constraints(output, max_target_weight=0.40)
        self.assertTrue(any("exceeds limit" in x for x in issues))

    def test_postcheck_detects_duplicate_ticker(self) -> None:
        output = RecommendationsOutput(
            recommendations=[
                RecommendationItem(
                    ticker="SPY",
                    action="HOLD",
                    confidence_score=0.6,
                    reasoning="Portfolio exposure is stable.",
                    constraints_check="No hard limits breached.",
                    target_weight=0.2,
                    horizon_days=20,
                ),
                RecommendationItem(
                    ticker="SPY",
                    action="SELL",
                    confidence_score=0.6,
                    reasoning="Long enough reasoning for a non-hold recommendation in this test case.",
                    constraints_check="No hard limits breached.",
                    target_weight=0.15,
                    horizon_days=20,
                ),
            ],
            global_summary="Duplicate ticker test.",
        )
        output.validate()
        issues = postcheck_recommendations(output)
        self.assertTrue(any("Duplicate ticker" in x for x in issues))


if __name__ == "__main__":
    unittest.main()

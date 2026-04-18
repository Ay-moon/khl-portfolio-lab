from __future__ import annotations

import sys
import unittest
from pathlib import Path

ANALYTICS_DIR = Path(__file__).resolve().parents[1]
if str(ANALYTICS_DIR) not in sys.path:
    sys.path.append(str(ANALYTICS_DIR))

from performance_risk_mvp import compute_daily_performance, compute_daily_risk


class PerformanceRiskMvpTests(unittest.TestCase):
    def test_compute_daily_performance_with_cash_and_market_value(self) -> None:
        date_keys = [20260102, 20260103, 20260104]
        market_values = {
            20260102: 1000.0,
            20260103: 1010.0,
            20260104: 1030.0,
        }
        cash_flows = {
            20260102: -1005.0,
        }

        rows = compute_daily_performance(
            date_keys=date_keys,
            market_values=market_values,
            cash_flows=cash_flows,
            initial_nav=100000.0,
        )

        self.assertEqual(len(rows), 3)
        self.assertAlmostEqual(rows[0].nav, 99995.0, places=6)
        self.assertAlmostEqual(rows[0].daily_pnl, -5.0, places=6)
        self.assertAlmostEqual(rows[1].daily_pnl, 10.0, places=6)
        self.assertAlmostEqual(rows[2].daily_pnl, 20.0, places=6)
        self.assertAlmostEqual(rows[2].cum_pnl, 25.0, places=6)

    def test_compute_daily_risk_has_expected_drawdown_and_nonpositive_var(self) -> None:
        perf_rows = compute_daily_performance(
            date_keys=[20260101, 20260102, 20260103, 20260104, 20260105],
            market_values={
                20260101: 100.0,
                20260102: 95.0,
                20260103: 97.0,
                20260104: 90.0,
                20260105: 93.0,
            },
            cash_flows={},
            initial_nav=0.0,
        )
        risk_rows = compute_daily_risk(perf_rows)

        self.assertEqual(len(risk_rows), len(perf_rows))
        self.assertAlmostEqual(risk_rows[-1].max_drawdown, -0.1, places=6)
        self.assertGreaterEqual(risk_rows[-1].volatility20d, 0.0)
        self.assertLessEqual(risk_rows[-1].var95, 0.0)


if __name__ == "__main__":
    unittest.main()


from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[1] / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.append(str(ENGINE_DIR))

from models import MarketOrder, PositionState
from simulator import TradingSimulator, build_daily_snapshots


class TradingSimulatorTests(unittest.TestCase):
    def test_buy_order_applies_fee_slippage_and_position_update(self) -> None:
        sim = TradingSimulator(fee_bps=10.0, slippage_bps=20.0)
        pos = PositionState()

        order = MarketOrder(
            trade_date=date(2026, 1, 5),
            ticker="AAPL",
            side="BUY",
            quantity=100.0,
        )
        trade = sim.execute_market_order(order, market_price=50.0, position=pos)

        self.assertAlmostEqual(trade.execution_price, 50.1, places=6)
        self.assertAlmostEqual(trade.gross_amount, 5010.0, places=6)
        self.assertAlmostEqual(trade.fee_amount, 5.01, places=6)
        self.assertAlmostEqual(trade.slippage_amount, 10.0, places=6)
        self.assertAlmostEqual(pos.quantity, 100.0, places=6)
        self.assertAlmostEqual(pos.avg_cost, 50.1501, places=6)

    def test_sell_order_reduces_position_and_keeps_avg_cost(self) -> None:
        sim = TradingSimulator(fee_bps=5.0, slippage_bps=10.0)
        pos = PositionState(quantity=20.0, avg_cost=10.0)

        order = MarketOrder(
            trade_date=date(2026, 1, 6),
            ticker="AAPL",
            side="SELL",
            quantity=5.0,
        )
        trade = sim.execute_market_order(order, market_price=12.0, position=pos)

        self.assertTrue(trade.execution_price < 12.0)
        self.assertAlmostEqual(pos.quantity, 15.0, places=6)
        self.assertAlmostEqual(pos.avg_cost, 10.0, places=6)

    def test_sell_more_than_position_raises(self) -> None:
        sim = TradingSimulator()
        pos = PositionState(quantity=2.0, avg_cost=15.0)

        order = MarketOrder(
            trade_date=date(2026, 1, 7),
            ticker="SPY",
            side="SELL",
            quantity=5.0,
        )

        with self.assertRaises(ValueError):
            sim.execute_market_order(order, market_price=100.0, position=pos)

    def test_daily_snapshot_weights_sum_to_one(self) -> None:
        positions = {
            "AAPL": PositionState(quantity=10.0, avg_cost=100.0),
            "MSFT": PositionState(quantity=20.0, avg_cost=50.0),
            "SPY": PositionState(quantity=0.0, avg_cost=0.0),
        }
        prices = {"AAPL": 120.0, "MSFT": 40.0, "SPY": 500.0}

        snapshots = build_daily_snapshots(date(2026, 1, 8), positions, prices)
        total_weight = sum(s.weight_pct for s in snapshots)

        self.assertEqual(len(snapshots), 2)
        self.assertAlmostEqual(total_weight, 1.0, places=6)


if __name__ == "__main__":
    unittest.main()

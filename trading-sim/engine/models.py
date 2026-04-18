from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class MarketOrder:
    trade_date: date
    ticker: str
    side: str
    quantity: float
    strategy_code: str = "SIM_MVP"
    order_type: str = "MARKET"

    def normalized_side(self) -> str:
        side = self.side.upper().strip()
        if side not in {"BUY", "SELL"}:
            raise ValueError(f"Unsupported order side: {self.side}")
        return side


@dataclass
class PositionState:
    quantity: float = 0.0
    avg_cost: float = 0.0

    def apply_buy(self, quantity: float, execution_price: float, fee_amount: float) -> None:
        if quantity <= 0:
            raise ValueError("Buy quantity must be > 0")
        total_cost_before = self.avg_cost * self.quantity
        gross = execution_price * quantity
        new_qty = self.quantity + quantity
        self.avg_cost = (total_cost_before + gross + fee_amount) / new_qty
        self.quantity = new_qty

    def apply_sell(self, quantity: float) -> None:
        if quantity <= 0:
            raise ValueError("Sell quantity must be > 0")
        if quantity > self.quantity + 1e-9:
            raise ValueError("Cannot sell more than current position")

        self.quantity -= quantity
        if abs(self.quantity) < 1e-9:
            self.quantity = 0.0
            self.avg_cost = 0.0


@dataclass
class ExecutedTrade:
    trade_date: date
    ticker: str
    side: str
    quantity: float
    market_price: float
    execution_price: float
    gross_amount: float
    fee_amount: float
    slippage_amount: float
    net_cash_flow: float
    strategy_code: str
    order_type: str


@dataclass
class PositionSnapshot:
    snapshot_date: date
    ticker: str
    quantity: float
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    weight_pct: float

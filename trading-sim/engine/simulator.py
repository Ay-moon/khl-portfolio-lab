from __future__ import annotations

from datetime import date

from models import ExecutedTrade, MarketOrder, PositionSnapshot, PositionState


class TradingSimulator:
    def __init__(self, fee_bps: float = 5.0, slippage_bps: float = 3.0) -> None:
        self.fee_bps = float(fee_bps)
        self.slippage_bps = float(slippage_bps)

    def execute_market_order(
        self,
        order: MarketOrder,
        market_price: float,
        position: PositionState,
    ) -> ExecutedTrade:
        side = order.normalized_side()
        if order.quantity <= 0:
            raise ValueError("Order quantity must be > 0")
        if market_price <= 0:
            raise ValueError("Market price must be > 0")

        slippage_rate = self.slippage_bps / 10000.0
        fee_rate = self.fee_bps / 10000.0

        if side == "BUY":
            execution_price = market_price * (1.0 + slippage_rate)
        else:
            execution_price = market_price * (1.0 - slippage_rate)

        gross_amount = order.quantity * execution_price
        fee_amount = gross_amount * fee_rate
        slippage_amount = abs(execution_price - market_price) * order.quantity

        if side == "BUY":
            position.apply_buy(order.quantity, execution_price, fee_amount)
            net_cash_flow = -(gross_amount + fee_amount)
        else:
            position.apply_sell(order.quantity)
            net_cash_flow = gross_amount - fee_amount

        return ExecutedTrade(
            trade_date=order.trade_date,
            ticker=order.ticker,
            side=side,
            quantity=order.quantity,
            market_price=market_price,
            execution_price=execution_price,
            gross_amount=gross_amount,
            fee_amount=fee_amount,
            slippage_amount=slippage_amount,
            net_cash_flow=net_cash_flow,
            strategy_code=order.strategy_code,
            order_type=order.order_type,
        )


def build_daily_snapshots(
    snapshot_date: date,
    positions: dict[str, PositionState],
    prices: dict[str, float],
) -> list[PositionSnapshot]:
    market_values: dict[str, float] = {}
    total_market_value = 0.0

    for ticker, pos in positions.items():
        if pos.quantity <= 0:
            continue
        px = prices[ticker]
        mv = pos.quantity * px
        market_values[ticker] = mv
        total_market_value += mv

    snapshots: list[PositionSnapshot] = []
    for ticker, mv in market_values.items():
        pos = positions[ticker]
        px = prices[ticker]
        unrealized = (px - pos.avg_cost) * pos.quantity
        weight = mv / total_market_value if total_market_value > 0 else 0.0
        snapshots.append(
            PositionSnapshot(
                snapshot_date=snapshot_date,
                ticker=ticker,
                quantity=pos.quantity,
                avg_cost=pos.avg_cost,
                market_value=mv,
                unrealized_pnl=unrealized,
                weight_pct=weight,
            )
        )

    return snapshots

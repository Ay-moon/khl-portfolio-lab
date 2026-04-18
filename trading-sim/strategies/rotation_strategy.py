from __future__ import annotations

from datetime import date

from models import MarketOrder, PositionState


class RotationStrategy:
    def __init__(self, strategy_code: str = "SIM_MVP", base_qty: float = 8.0) -> None:
        self.strategy_code = strategy_code
        self.base_qty = base_qty

    def build_orders(
        self,
        day_index: int,
        trade_date: date,
        prices: dict[str, float],
        positions: dict[str, PositionState],
    ) -> list[MarketOrder]:
        tickers = sorted(prices.keys())
        primary = tickers[day_index % len(tickers)]
        orders: list[MarketOrder] = []

        if day_index < 20 or day_index % 4 != 0:
            qty = self.base_qty + (day_index % 3)
            orders.append(
                MarketOrder(
                    trade_date=trade_date,
                    ticker=primary,
                    side="BUY",
                    quantity=qty,
                    strategy_code=self.strategy_code,
                    order_type="MARKET",
                )
            )
        else:
            held = positions.get(primary, PositionState()).quantity
            if held >= 4.0:
                orders.append(
                    MarketOrder(
                        trade_date=trade_date,
                        ticker=primary,
                        side="SELL",
                        quantity=min(6.0, held),
                        strategy_code=self.strategy_code,
                        order_type="MARKET",
                    )
                )
            else:
                orders.append(
                    MarketOrder(
                        trade_date=trade_date,
                        ticker=primary,
                        side="BUY",
                        quantity=5.0,
                        strategy_code=self.strategy_code,
                        order_type="MARKET",
                    )
                )

        if day_index % 10 == 0 and "SPY" in prices:
            orders.append(
                MarketOrder(
                    trade_date=trade_date,
                    ticker="SPY",
                    side="BUY",
                    quantity=2.0,
                    strategy_code=self.strategy_code,
                    order_type="MARKET",
                )
            )

        return orders

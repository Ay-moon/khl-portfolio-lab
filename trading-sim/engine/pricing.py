from __future__ import annotations

import random
from datetime import date, timedelta


def business_days(start_date: date, count: int) -> list[date]:
    days: list[date] = []
    current = start_date
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def generate_price_grid(
    tickers: list[str],
    start_date: date,
    days: int,
    seed: int = 17,
) -> tuple[list[date], dict[date, dict[str, float]]]:
    rng = random.Random(seed)
    calendar = business_days(start_date, days)

    base = {
        "AAPL": 185.0,
        "MSFT": 415.0,
        "SPY": 500.0,
    }

    last_prices: dict[str, float] = {
        ticker: base.get(ticker, 100.0 + (idx * 25.0))
        for idx, ticker in enumerate(tickers)
    }

    by_day: dict[date, dict[str, float]] = {}
    for _day in calendar:
        day_prices: dict[str, float] = {}
        for ticker in tickers:
            drift = 0.0004
            noise = rng.uniform(-0.01, 0.01)
            new_price = max(1.0, last_prices[ticker] * (1.0 + drift + noise))
            new_price = round(new_price, 6)
            day_prices[ticker] = new_price
            last_prices[ticker] = new_price
        by_day[_day] = day_prices

    return calendar, by_day

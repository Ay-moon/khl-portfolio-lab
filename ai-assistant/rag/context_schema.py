from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PortfolioHeadline:
    date_key: int
    full_date: str | None
    nav: float
    daily_pnl: float
    cum_pnl: float
    return_pct: float
    volatility20d: float
    max_drawdown: float
    var95: float
    sharpe_ratio: float


@dataclass
class PositionLine:
    ticker: str
    security_name: str
    quantity: float
    market_value: float
    unrealized_pnl: float
    weight_pct: float


@dataclass
class LatestRecommendationLine:
    ticker: str | None
    action: str
    confidence_score: float | None
    status: str
    created_at: str | None


@dataclass
class ContextPack:
    portfolio_code: str
    date_key: int
    headline: PortfolioHeadline
    positions: list[PositionLine]
    latest_recommendations: list[LatestRecommendationLine]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

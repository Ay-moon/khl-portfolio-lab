from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ALLOWED_ACTIONS = {"BUY", "SELL", "HOLD", "REDUCE", "INCREASE"}


def _validate_ticker(ticker: str) -> None:
    cleaned = ticker.strip().upper()
    if not cleaned:
        raise ValueError("Ticker must be non-empty")
    if len(cleaned) > 20:
        raise ValueError(f"Ticker too long: {cleaned}")
    for ch in cleaned:
        if ch.isalnum() or ch in {"_", "-", "."}:
            continue
        raise ValueError(f"Ticker has unsupported character '{ch}': {cleaned}")


@dataclass
class DailyBriefingOutput:
    market_regime: str
    summary: str
    assumptions: list[str]
    focus_tickers: list[str]
    confidence: float

    def validate(self) -> None:
        if not self.market_regime.strip():
            raise ValueError("market_regime is required")
        if not self.summary.strip():
            raise ValueError("summary is required")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if len(self.assumptions) == 0:
            raise ValueError("assumptions cannot be empty")
        for ticker in self.focus_tickers:
            _validate_ticker(ticker)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecommendationItem:
    ticker: str
    action: str
    confidence_score: float
    reasoning: str
    constraints_check: str
    target_weight: float | None = None
    horizon_days: int | None = None

    def validate(self) -> None:
        _validate_ticker(self.ticker)
        action = self.action.strip().upper()
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported recommendation action: {self.action}")
        if not 0.0 <= float(self.confidence_score) <= 1.0:
            raise ValueError("confidence_score must be in [0, 1]")
        if not self.reasoning.strip():
            raise ValueError("reasoning is required")
        if not self.constraints_check.strip():
            raise ValueError("constraints_check is required")
        if self.target_weight is not None and not 0.0 <= float(self.target_weight) <= 1.0:
            raise ValueError("target_weight must be in [0, 1]")
        if self.horizon_days is not None and int(self.horizon_days) <= 0:
            raise ValueError("horizon_days must be > 0")

    def normalized_action(self) -> str:
        return self.action.strip().upper()


@dataclass
class RecommendationsOutput:
    recommendations: list[RecommendationItem]
    global_summary: str

    def validate(self) -> None:
        if not self.global_summary.strip():
            raise ValueError("global_summary is required")
        if len(self.recommendations) == 0:
            raise ValueError("recommendations cannot be empty")
        for rec in self.recommendations:
            rec.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendations": [asdict(x) for x in self.recommendations],
            "global_summary": self.global_summary,
        }


@dataclass
class WhatIfOutput:
    scenario_name: str
    narrative: str
    expected_volatility_delta: float | None
    expected_return_delta: float | None

    def validate(self) -> None:
        if not self.scenario_name.strip():
            raise ValueError("scenario_name is required")
        if not self.narrative.strip():
            raise ValueError("narrative is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

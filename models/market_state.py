from dataclasses import dataclass


@dataclass
class MarketState:

    trend: str

    strength: float

    volatility: float

    momentum: float

    confidence: float

    reasons: list[str]
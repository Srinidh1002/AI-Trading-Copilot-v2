from dataclasses import dataclass, field


@dataclass
class MarketRegime:
    primary_regime: str
    trend: str
    volatility: str
    confidence: int
    score: int
    metrics: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
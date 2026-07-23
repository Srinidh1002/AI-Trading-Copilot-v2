from dataclasses import dataclass, field


@dataclass
class Score:

    trend: str = "NEUTRAL"

    strength: int = 0

    momentum: int = 0

    volatility: int = 0

    confidence: int = 0

    reasons: list[str] = field(default_factory=list)
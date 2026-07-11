from dataclasses import dataclass, field


@dataclass
class StrategyState:
    strategy: str
    direction: str
    confidence: int
    decision: str
    bullish_score: int
    bearish_score: int
    confirmations: list[str] = field(
        default_factory=list
    )
    risk_flags: list[str] = field(
        default_factory=list
    )
    suitable_strategies: list[str] = field(
        default_factory=list
    )
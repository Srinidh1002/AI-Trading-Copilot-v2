from dataclasses import dataclass, field


@dataclass
class OptionsRiskState:
    approved: bool
    decision: str
    lots: int
    quantity: int
    premium_exposure: float
    spread_percent: float
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
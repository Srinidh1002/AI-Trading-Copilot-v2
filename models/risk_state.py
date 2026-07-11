from dataclasses import dataclass, field


@dataclass
class RiskState:
    approved: bool
    decision: str
    position_size: int
    risk_amount: float
    risk_reward_ratio: float
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
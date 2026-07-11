from dataclasses import dataclass, field


@dataclass
class FinalDecisionState:
    decision: str
    action: str
    direction: str
    strategy: str
    confidence: int
    approved: bool
    reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
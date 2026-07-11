from dataclasses import dataclass, field


@dataclass
class OptionContractState:
    selected: bool
    decision: str
    symbol: str | None
    strike: float | None
    option_type: str | None
    expiry: str | None
    premium: float | None
    score: int
    reasons: list[str] = field(default_factory=list)
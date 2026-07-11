"""Domain model for a trading recommendation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


Action = Literal["BUY CE", "BUY PE", "NO TRADE"]
_VALID_ACTIONS: frozenset[str] = frozenset({"BUY CE", "BUY PE", "NO TRADE"})


@dataclass
class Recommendation:
    """A validated trade recommendation with risk and target information."""

    symbol: str
    action: Action
    entry: float
    stop_loss: float
    target1: float
    target2: float
    confidence: int
    risk_reward: float
    reasons: list[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Reject action values outside the supported trading decisions."""

        if self.action not in _VALID_ACTIONS:
            allowed = ", ".join(sorted(_VALID_ACTIONS))
            raise ValueError(f"action must be one of: {allowed}")

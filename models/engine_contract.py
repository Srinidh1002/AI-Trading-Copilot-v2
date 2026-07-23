"""
Standard Engine Output Contract

Every AI engine in the trading system should return this structure.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EngineResult:
    """
    Standard return object shared by every engine.
    """

    signal: str = "HOLD"
    trend: str = "NEUTRAL"

    bull_score: float = 0.0
    bear_score: float = 0.0
    confidence: float = 0.0

    reasons: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal,
            "trend": self.trend,
            "bull_score": self.bull_score,
            "bear_score": self.bear_score,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "metadata": self.metadata,
        }
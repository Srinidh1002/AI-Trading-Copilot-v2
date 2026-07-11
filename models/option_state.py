"""Domain model for option-chain analysis results."""

from dataclasses import dataclass


@dataclass
class OptionState:
    """Key support, resistance, and sentiment data from an option chain."""

    pcr: float
    support: int
    resistance: int
    max_pain: int
    score: int
    confidence: int
    reasons: list[str]

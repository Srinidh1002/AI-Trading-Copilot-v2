"""Domain model for a technical market analysis result."""

from dataclasses import dataclass


@dataclass
class TechnicalState:
    """Technical signals and their supporting indicator values."""

    trend: str
    score: int
    confidence: int
    reasons: list[str]
    indicators: dict

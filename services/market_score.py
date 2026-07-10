from dataclasses import dataclass


@dataclass
class Score:

    trend = "NEUTRAL"

    strength = 0

    momentum = 0

    volatility = 0

    confidence = 0

    reasons = []
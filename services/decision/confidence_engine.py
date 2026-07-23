"""
Confidence Engine V2
"""

from services.analysis.candlestick_engine import detect_pattern
from archive.pattern_score import pattern_score
from archive.pattern_score import pattern_score
from archive.pattern_score import pattern_score

def calculate_confidence(snapshot, trend):

    history = snapshot["history"]

    candle = detect_pattern(history)

    pattern = pattern_score(candle)

    score = 0

    # Trend
    if trend["trend"] in ("Bullish", "Bearish"):
        score += 25

    # Momentum
    if trend["momentum"] in ("Bullish", "Bearish"):
        score += 20
    else:
        score += 10

    # Strength
    strength_points = {
        "Very Strong": 25,
        "Strong": 20,
        "Moderate": 15,
        "Weak": 5,
    }

    score += strength_points.get(trend["strength"], 0)

    # Pattern
    score += pattern["score"]

    return min(score, 100)
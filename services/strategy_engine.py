"""
Strategy Engine
Combines all AI modules into one final decision.
"""


def _score(data, key, default=0):
    try:
        return int(data.get(key, default))
    except (AttributeError, TypeError, ValueError):
        return default


def strategy_engine(technical, market, option, sentiment):

    technical = technical if isinstance(technical, dict) else {}
    market = market if isinstance(market, dict) else {}
    option = option if isinstance(option, dict) else {}
    sentiment = sentiment if isinstance(sentiment, dict) else {}

    bull = (
        _score(technical, "bull")
        + _score(option, "bull")
    )

    bear = (
        _score(technical, "bear")
        + _score(option, "bear")
    )

    confidence = _score(market, "confidence")

    if market.get("trend") == "Bullish":
        bull += confidence
    elif market.get("trend") == "Bearish":
        bear += confidence

    sentiment_points = _score(sentiment, "score", 50)

    bull += sentiment_points
    bear += (100 - sentiment_points)

    if bull > bear:
        signal = "BUY"
    elif bear > bull:
        signal = "SELL"
    else:
        signal = "HOLD"

    return {
        "signal": signal,
        "bull": bull,
        "bear": bear,
        "confidence": abs(bull - bear)
    }
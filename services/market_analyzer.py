"""Rule-based analysis of major Indian market indices."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from services.market_indices import market_indices


Trend = Literal["BULLISH", "BEARISH", "NEUTRAL"]


class MarketAnalysis(TypedDict):
    """Normalised market regime returned to trading agents."""

    trend: Trend
    strength: int
    volatility: int
    momentum: int
    confidence: int
    reasons: list[str]


def _clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    """Convert a score to the public 0--100 range."""

    return max(minimum, min(maximum, round(value)))


def _change_percent(index: object) -> float | None:
    """Calculate an index's percentage move from its price and point change.

    ``market_indices`` supplies the current price and absolute change, rather
    than a percentage.  Invalid or unavailable values return ``None`` so they
    do not affect the directional score.
    """

    if not isinstance(index, dict):
        return None

    try:
        price = float(index.get("price", 0))
        change = float(index.get("change", 0))
        previous_close = price - change
    except (TypeError, ValueError):
        return None

    if price <= 0 or previous_close <= 0:
        return None

    return (change / previous_close) * 100


def _vix_value(index: object) -> float | None:
    """Return the current India VIX value when it is usable."""

    if not isinstance(index, dict):
        return None

    try:
        value = float(index.get("price", 0))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def analyse_market() -> MarketAnalysis:
    """Evaluate index direction, momentum, volatility, and confidence.

    A NIFTY move beyond +/-1% contributes 30 points and a BANKNIFTY move
    beyond +/-1% contributes 20 points to the directional score.  India VIX
    adjusts confidence: below 15 improves it, while above 20 reduces it.
    """

    analysis: MarketAnalysis = {
        "trend": "NEUTRAL",
        "strength": 0,
        "volatility": 0,
        "momentum": 0,
        "confidence": 50,
        "reasons": [],
    }

    data: dict[str, Any] = market_indices()
    if not data:
        analysis["reasons"].append("No market data is available.")
        return analysis

    directional_score = 0
    for name, weight in (("nifty", 30), ("banknifty", 20)):
        move = _change_percent(data.get(name))
        display_name = "NIFTY" if name == "nifty" else "BANKNIFTY"
        if move is None:
            analysis["reasons"].append(f"{display_name} data is unavailable.")
        elif move > 1:
            directional_score += weight
            analysis["reasons"].append(
                f"{display_name} is up {move:.2f}%, adding bullish momentum."
            )
        elif move < -1:
            directional_score -= weight
            analysis["reasons"].append(
                f"{display_name} is down {abs(move):.2f}%, adding bearish momentum."
            )
        else:
            analysis["reasons"].append(
                f"{display_name} is range-bound at {move:+.2f}%."
            )

    if directional_score > 0:
        analysis["trend"] = "BULLISH"
    elif directional_score < 0:
        analysis["trend"] = "BEARISH"

    analysis["strength"] = _clamp(abs(directional_score) * 2)
    analysis["momentum"] = _clamp(50 + directional_score)

    vix = _vix_value(data.get("vix"))
    if vix is None:
        analysis["reasons"].append("India VIX data is unavailable.")
    else:
        analysis["volatility"] = _clamp((vix / 30) * 100)
        if vix > 20:
            analysis["confidence"] = 30
            analysis["reasons"].append(
                f"India VIX is elevated at {vix:.2f}; confidence is reduced."
            )
        elif vix < 15:
            analysis["confidence"] = 70
            analysis["reasons"].append(
                f"India VIX is low at {vix:.2f}; confidence is increased."
            )
        else:
            analysis["reasons"].append(
                f"India VIX is moderate at {vix:.2f}."
            )

    return analysis

"""Combine market, technical, and option states into a trade recommendation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Literal

from models.market_state import MarketState
from models.option_state import OptionState
from models.recommendation import Recommendation
from models.technical_state import TechnicalState


Bias = Literal["BULLISH", "BEARISH", "NEUTRAL"]


def _clamp_confidence(value: float) -> int:
    """Return a rounded confidence percentage in the public 0--100 range."""

    return max(0, min(100, round(value)))


def _valid_number(value: object) -> float | None:
    """Return a positive finite number, or ``None`` when it is unusable."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _normalise_bias(trend: object) -> Bias:
    """Map state trend strings to the decision engine's supported biases."""

    value = str(trend).upper()
    if value == "BULLISH":
        return "BULLISH"
    if value == "BEARISH":
        return "BEARISH"
    return "NEUTRAL"


def _option_bias(score: object) -> Bias:
    """Derive option-chain direction from its 0--100 sentiment score."""

    try:
        value = float(score)
    except (TypeError, ValueError):
        return "NEUTRAL"
    if value > 50:
        return "BULLISH"
    if value < 50:
        return "BEARISH"
    return "NEUTRAL"


def _entry_reference(technical: TechnicalState, option: OptionState) -> float | None:
    """Choose the best available price proxy for entry-level calculations."""

    indicators = technical.indicators
    if isinstance(indicators, Mapping):
        for name in ("vwap", "ema20", "ema50", "ema200"):
            value = _valid_number(indicators.get(name))
            if value is not None:
                return value

    for value in (
        option.max_pain,
        (option.support + option.resistance) / 2
        if option.support > 0 and option.resistance > 0
        else None,
    ):
        reference = _valid_number(value)
        if reference is not None:
            return reference
    return None


def _levels(action: Literal["BUY CE", "BUY PE"], entry: float, option: OptionState) -> tuple[float, float, float, float]:
    """Calculate stop, two targets, and risk/reward from option-chain levels."""

    minimum_risk = max(entry * 0.01, 0.01)
    if action == "BUY CE":
        stop_loss = float(option.support) if 0 < option.support < entry else entry - minimum_risk
        risk = entry - stop_loss
        target1 = (
            float(option.resistance)
            if option.resistance > entry
            else entry + (risk * 1.5)
        )
        target2 = max(target1, entry + (risk * 2))
        risk_reward = (target1 - entry) / risk
    else:
        stop_loss = (
            float(option.resistance)
            if option.resistance > entry
            else entry + minimum_risk
        )
        risk = stop_loss - entry
        target1 = (
            float(option.support)
            if 0 < option.support < entry
            else max(0.0, entry - (risk * 1.5))
        )
        target2 = min(target1, max(0.0, entry - (risk * 2)))
        risk_reward = (entry - target1) / risk

    return (
        round(stop_loss, 2),
        round(target1, 2),
        round(target2, 2),
        round(risk_reward, 2),
    )


def decide(
    market_state: MarketState,
    technical_state: TechnicalState,
    option_state: OptionState,
    symbol: str = "NIFTY",
) -> Recommendation:
    """Create a recommendation when market, technical, and option bias agree.

    A trade requires all three state biases to be bullish or bearish and their
    average confidence to be at least 70.  The entry reference is the latest
    available VWAP/EMA, with option-chain levels used as a fallback.  Support
    and resistance determine the initial stop loss and profit targets.
    """

    market_bias = _normalise_bias(market_state.trend)
    technical_bias = _normalise_bias(technical_state.trend)
    option_bias = _option_bias(option_state.score)
    confidence = _clamp_confidence(
        (float(market_state.confidence) + float(technical_state.confidence) + float(option_state.confidence))
        / 3
    )
    reasons = [
        f"Market trend is {market_bias}.",
        f"Technical trend is {technical_bias}.",
        f"Option-chain bias is {option_bias}.",
        f"Combined confidence is {confidence}%.",
    ]

    action: Literal["BUY CE", "BUY PE", "NO TRADE"] = "NO TRADE"
    if confidence < 70:
        reasons.append("No trade: combined confidence is below 70%.")
    elif (market_bias, technical_bias, option_bias) == (
        "BULLISH",
        "BULLISH",
        "BULLISH",
    ):
        action = "BUY CE"
        reasons.append("All three analyses are bullish.")
    elif (market_bias, technical_bias, option_bias) == (
        "BEARISH",
        "BEARISH",
        "BEARISH",
    ):
        action = "BUY PE"
        reasons.append("All three analyses are bearish.")
    else:
        reasons.append("No trade: market, technical, and option signals do not align.")

    if action == "NO TRADE":
        return Recommendation(
            symbol=symbol,
            action=action,
            entry=0.0,
            stop_loss=0.0,
            target1=0.0,
            target2=0.0,
            confidence=confidence,
            risk_reward=0.0,
            reasons=reasons,
        )

    entry = _entry_reference(technical_state, option_state)
    if entry is None:
        reasons.append("No trade: a valid entry price reference is unavailable.")
        return Recommendation(
            symbol=symbol,
            action="NO TRADE",
            entry=0.0,
            stop_loss=0.0,
            target1=0.0,
            target2=0.0,
            confidence=confidence,
            risk_reward=0.0,
            reasons=reasons,
        )

    stop_loss, target1, target2, risk_reward = _levels(action, entry, option_state)
    return Recommendation(
        symbol=symbol,
        action=action,
        entry=round(entry, 2),
        stop_loss=stop_loss,
        target1=target1,
        target2=target2,
        confidence=confidence,
        risk_reward=risk_reward,
        reasons=reasons,
    )


def decision_engine(
    market_state: MarketState,
    technical_state: TechnicalState,
    option_state: OptionState,
    symbol: str = "NIFTY",
) -> Recommendation:
    """Compatibility entry point for callers using the service module name."""

    return decide(market_state, technical_state, option_state, symbol)

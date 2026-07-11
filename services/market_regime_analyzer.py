"""
Market regime detection engine.

Classifies the current market environment using:
- EMA structure
- ADX trend strength
- ATR volatility
- Bollinger Band width
- Price structure
"""

import pandas as pd


VALID_REGIMES = {
    "TRENDING_BULLISH",
    "TRENDING_BEARISH",
    "RANGING",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "COMPRESSION",
    "UNCERTAIN",
}


def analyse_market_regime(data: pd.DataFrame) -> dict:
    required_columns = {
        "Close",
        "EMA20",
        "EMA50",
        "ATR",
        "ADX",
        "BB_UPPER",
        "BB_LOWER",
    }

    if data is None or data.empty:
        raise ValueError("No market data provided.")

    missing = required_columns - set(data.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    latest = data.iloc[-1]

    close = float(latest["Close"])
    ema20 = float(latest["EMA20"])
    ema50 = float(latest["EMA50"])
    atr = float(latest["ATR"])
    adx = float(latest["ADX"])
    bb_upper = float(latest["BB_UPPER"])
    bb_lower = float(latest["BB_LOWER"])

    if close <= 0:
        raise ValueError("Close price must be greater than zero.")

    reasons = []
    score = 0

    # -------------------------
    # TREND
    # -------------------------

    if close > ema20 > ema50:
        trend = "BULLISH"
        score += 3
        reasons.append(
            "Price is above EMA20 and EMA20 is above EMA50."
        )

    elif close < ema20 < ema50:
        trend = "BEARISH"
        score -= 3
        reasons.append(
            "Price is below EMA20 and EMA20 is below EMA50."
        )

    else:
        trend = "NEUTRAL"
        reasons.append(
            "EMA structure does not show a clear trend."
        )

    # -------------------------
    # TREND STRENGTH
    # -------------------------

    if adx >= 25:
        reasons.append(
            f"ADX {adx:.2f} indicates a strong trend."
        )
    else:
        reasons.append(
            f"ADX {adx:.2f} indicates weak trend strength."
        )

    # -------------------------
    # VOLATILITY
    # -------------------------

    atr_percent = (atr / close) * 100

    if atr_percent >= 2:
        volatility = "HIGH"
        reasons.append(
            f"ATR is {atr_percent:.2f}% of price."
        )

    elif atr_percent <= 0.5:
        volatility = "LOW"
        reasons.append(
            f"ATR is only {atr_percent:.2f}% of price."
        )

    else:
        volatility = "NORMAL"

    # -------------------------
    # BOLLINGER BAND WIDTH
    # -------------------------

    bb_width_percent = (
        (bb_upper - bb_lower) / close
    ) * 100

    compression = bb_width_percent <= 2

    if compression:
        reasons.append(
            "Bollinger Band width indicates price compression."
        )

    # -------------------------
    # PRIMARY REGIME
    # -------------------------

    if compression and adx < 25:
        primary_regime = "COMPRESSION"

    elif volatility == "HIGH":
        primary_regime = "HIGH_VOLATILITY"

    elif (
        trend == "BULLISH"
        and adx >= 25
    ):
        primary_regime = "TRENDING_BULLISH"

    elif (
        trend == "BEARISH"
        and adx >= 25
    ):
        primary_regime = "TRENDING_BEARISH"

    elif (
        adx < 20
        and trend == "NEUTRAL"
    ):
        primary_regime = "RANGING"

    elif volatility == "LOW":
        primary_regime = "LOW_VOLATILITY"

    else:
        primary_regime = "UNCERTAIN"

    # -------------------------
    # CONFIDENCE
    # -------------------------

    confidence = 50

    if primary_regime in {
        "TRENDING_BULLISH",
        "TRENDING_BEARISH",
    }:
        confidence += min(
            int(adx - 25),
            30,
        )

    if primary_regime == "COMPRESSION":
        confidence += 20

    if primary_regime == "RANGING":
        confidence += 15

    confidence = max(
        0,
        min(100, confidence),
    )

    return {
        "primary_regime": primary_regime,
        "trend": trend,
        "volatility": volatility,
        "confidence": confidence,
        "score": score,
        "metrics": {
            "adx": adx,
            "atr_percent": round(
                atr_percent,
                2,
            ),
            "bb_width_percent": round(
                bb_width_percent,
                2,
            ),
        },
        "reasons": reasons,
    }
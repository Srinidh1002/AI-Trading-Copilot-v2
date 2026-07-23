"""
Market Regime Engine

Determines the current market regime using
trend, volatility and momentum.
"""


def analyze_market_regime(snapshot):

    indicators = snapshot.get(
        "indicators",
        {},
    )

    close = indicators.get(
        "CLOSE",
        0,
    )

    ema20 = indicators.get(
        "EMA20",
        close,
    )

    ema50 = indicators.get(
        "EMA50",
        close,
    )

    ema200 = indicators.get(
        "EMA200",
        close,
    )

    adx = indicators.get(
        "ADX",
        20,
    )

    atr = indicators.get(
        "ATR",
        0,
    )

    bull = 0
    bear = 0

    reasons = []

    # -------------------------
    # Trend
    # -------------------------

    if ema20 > ema50 > ema200:

        bull += 4

        reasons.append(
            "Strong Uptrend"
        )

    elif ema20 < ema50 < ema200:

        bear += 4

        reasons.append(
            "Strong Downtrend"
        )

    else:

        reasons.append(
            "Sideways Trend"
        )

    # -------------------------
    # ADX
    # -------------------------

    if adx >= 30:

        bull += 2

        reasons.append(
            "Strong Trend Strength"
        )

    elif adx <= 18:

        reasons.append(
            "Weak Trend"
        )

    # -------------------------
    # ATR
    # -------------------------

    volatility = "LOW"

    if atr > 0:

        volatility_pct = (atr / close) * 100

        if volatility_pct >= 2:

            volatility = "HIGH"

            bear += 1

            reasons.append(
                "High Volatility"
            )

        elif volatility_pct >= 1:

            volatility = "NORMAL"

        else:

            volatility = "LOW"

            bull += 1

            reasons.append(
                "Stable Volatility"
            )

    # -------------------------

    if bull >= bear + 2:

        regime = "TRENDING_BULLISH"

    elif bear >= bull + 2:

        regime = "TRENDING_BEARISH"

    else:

        regime = "RANGE_BOUND"

    confidence = min(
        100,
        55 + abs(bull - bear) * 8,
    )

    return {

        "signal": regime,

        "bull_score": bull,

        "bear_score": bear,

        "confidence": round(
            confidence,
            2,
        ),

        "reason": ", ".join(reasons),

        "metrics": {

            "EMA20": ema20,

            "EMA50": ema50,

            "EMA200": ema200,

            "ADX": adx,

            "ATR": atr,

            "Volatility": volatility,

        },

    }
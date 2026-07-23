def analyze_trend(snapshot):
    """
    Analyze overall market trend using the latest indicator values.
    """

    indicators = snapshot["indicators"]

    ema20 = float(indicators["EMA20"])
    ema50 = float(indicators["EMA50"])
    ema200 = float(indicators["EMA200"])

    macd = float(indicators["MACD"])
    macd_signal = float(indicators["MACD_SIGNAL"])

    adx = float(indicators["ADX"])

    vwap = float(indicators["VWAP"])
    close = float(indicators["CLOSE"])

    bull_score = 0
    bear_score = 0
    reasons = []

    # EMA

    if ema20 > ema50 > ema200:
        bull_score += 3
        reasons.append("EMA Bullish")

    elif ema20 < ema50 < ema200:
        bear_score += 3
        reasons.append("EMA Bearish")

    # MACD

    if macd > macd_signal:
        bull_score += 2
        reasons.append("MACD Bullish")

    elif macd < macd_signal:
        bear_score += 2
        reasons.append("MACD Bearish")

    # VWAP

    if vwap == vwap:

        if close > vwap:
            bull_score += 1
            reasons.append("Above VWAP")

        elif close < vwap:
            bear_score += 1
            reasons.append("Below VWAP")

    # ADX

    if adx >= 30:

        if bull_score > bear_score:
            bull_score += 1

        elif bear_score > bull_score:
            bear_score += 1

        reasons.append("Strong Trend")

    elif adx < 20:
        reasons.append("Weak Trend")

    # Confidence

    dominance = abs(bull_score - bear_score)

    confidence = min(
        100,
        round((adx * 1.5) + (dominance * 8), 2),
    )

    # Signal

    if bull_score >= bear_score + 2:
        signal = "BULLISH"

    elif bear_score >= bull_score + 2:
        signal = "BEARISH"

    else:
        signal = "SIDEWAYS"

    return {
        "signal": signal,
        "bull_score": bull_score,
        "bear_score": bear_score,
        "confidence": confidence,
        "reason": ", ".join(reasons),
    }
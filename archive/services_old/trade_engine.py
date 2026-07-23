from services.decision.risk_management import calculate_trade_levels
from services.analysis.candlestick_engine import detect_pattern
from archive.pattern_score import pattern_score
from services.decision.confidence_engine import calculate_confidence
from services.analysis.trend_engine import analyze_trend
from services.analysis.support_resistance_engine import calculate_support_resistance


def analyze_trade(snapshot):

    trend = analyze_trend(snapshot)

    history = snapshot["history"]

    sr = calculate_support_resistance(history)

    candle = detect_pattern(history)

    pattern = pattern_score(candle)

    confidence = calculate_confidence(
        trend=trend["trend"],
        momentum=trend["momentum"],
        strength=trend["strength"],
        pattern_score=pattern["score"],
    )

    trade = calculate_trade_levels(
        snapshot["ltp"],
        sr["Support"],
        sr["Resistance"],
    )

    if trend["trend"] == "Bullish" and confidence >= 75:
        decision = "BUY"

    elif trend["trend"] == "Bearish" and confidence >= 75:
        decision = "SELL"

    else:
        decision = "HOLD"

    return {
        "decision": decision,

        "trend": trend["trend"],
        "strength": trend["strength"],
        "momentum": trend["momentum"],

        "pattern": candle["pattern"],
        "pattern_bias": pattern["bias"],

        "support": sr["Support"],
        "resistance": sr["Resistance"],
        "current_price": snapshot["ltp"],

        "confidence": confidence,

        "reasons": [
            f"Trend: {trend['trend']}",
            f"Momentum: {trend['momentum']}",
            f"Pattern: {candle['pattern']}",
            f"Pattern Bias: {pattern['bias']}",
        ],

        "entry": trade["ENTRY"],
        "stop_loss": trade["STOP_LOSS"],
        "target1": trade["TARGET1"],
        "target2": trade["TARGET2"],
        "risk_reward": trade["RR"],
    }
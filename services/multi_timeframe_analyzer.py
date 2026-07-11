"""
Multi-timeframe market analysis.
"""

from services.technical_analyzer import analyse_technical


TIMEFRAME_WEIGHTS = {
    "5m": 0.15,
    "15m": 0.25,
    "1h": 0.35,
    "1d": 0.25,
}


def analyse_multi_timeframe(timeframes):
    """
    Analyse multiple OHLCV DataFrames and determine trend alignment.

    Expected input:
    {
        "5m": dataframe,
        "15m": dataframe,
        "1h": dataframe,
        "1d": dataframe,
    }
    """

    if not timeframes:
        raise ValueError("No timeframe data provided.")

    results = {}
    bullish_weight = 0.0
    bearish_weight = 0.0
    analysed_weight = 0.0

    for timeframe, weight in TIMEFRAME_WEIGHTS.items():
        df = timeframes.get(timeframe)

        if df is None or df.empty:
            continue

        analysis = analyse_technical(df)

        results[timeframe] = analysis
        analysed_weight += weight

        trend = analysis["trend"].upper()

        if trend == "BULLISH":
            bullish_weight += weight

        elif trend == "BEARISH":
            bearish_weight += weight

    if not results:
        raise ValueError("No valid timeframe data available.")

    bullish_score = bullish_weight / analysed_weight
    bearish_score = bearish_weight / analysed_weight

    if bullish_score >= 0.70:
        overall_trend = "BULLISH"
    elif bearish_score >= 0.70:
        overall_trend = "BEARISH"
    else:
        overall_trend = "MIXED"

    confidence = round(
        max(bullish_score, bearish_score) * 100
    )

    trends = {
        result["trend"].upper()
        for result in results.values()
    }

    if len(trends) == 1:
        alignment = "FULL"
    elif overall_trend in {"BULLISH", "BEARISH"}:
        alignment = "PARTIAL"
    else:
        alignment = "CONFLICTED"

    reasons = [
        f"{timeframe}: {result['trend']}"
        for timeframe, result in results.items()
    ]

    return {
        "overall_trend": overall_trend,
        "confidence": confidence,
        "alignment": alignment,
        "timeframe_results": results,
        "reasons": reasons,
    }
"""
Decision Quality Engine

Evaluates the overall quality of the final trading
decision before execution.
"""


def analyze_decision_quality(snapshot):

    """
    Expected snapshot

    snapshot should contain completed analysis results:

    trend_analysis
    structure_analysis
    candlestick_analysis
    volume_analysis
    market_breadth_analysis
    fii_dii_analysis
    vix_analysis
    market_strength_analysis
    confluence_analysis
    self_validation_analysis
    """

    modules = [

        snapshot.get("trend_analysis", {}),
        snapshot.get("structure_analysis", {}),
        snapshot.get("candlestick_analysis", {}),
        snapshot.get("volume_analysis", {}),
        snapshot.get("market_breadth_analysis", {}),
        snapshot.get("market_regime_analysis", {}),
        snapshot.get("liquidity_analysis", {}),
        snapshot.get("correlation_analysis", {}),
        snapshot.get("fii_dii_analysis", {}),
        snapshot.get("vix_analysis", {}),
        snapshot.get("news_analysis", {}),
        snapshot.get("economic_analysis", {}),
        snapshot.get("market_strength_analysis", {}),
        snapshot.get("execution_quality_analysis", {}),
        snapshot.get("portfolio_risk_analysis", {}),
        snapshot.get("confluence_analysis", {}),
        snapshot.get("self_validation_analysis", {}),

    ]

    active = 0
    confidence_sum = 0

    bullish = 0
    bearish = 0

    strong_modules = 0

    for module in modules:

        if not module:
            continue

        active += 1

        confidence = module.get(
            "confidence",
            0,
        )

        confidence_sum += confidence

        bullish += module.get(
            "bull_score",
            0,
        )

        bearish += module.get(
            "bear_score",
            0,
        )

        if confidence >= 80:
            strong_modules += 1

    if active == 0:

        return {

            "signal": "UNKNOWN",

            "quality": 0,

            "confidence": 0,

            "reason": "No analysis available",

            "metrics": {},

        }

    avg_confidence = confidence_sum / active

    agreement = abs(
        bullish - bearish
    )

    quality = (

        avg_confidence * 0.60

        +

        min(
            agreement,
            100,
        ) * 0.25

        +

        (

            strong_modules

            / active

        ) * 100 * 0.15

    )

    quality = round(

        min(
            quality,
            100,
        ),

        2,

    )

    if quality >= 90:

        signal = "INSTITUTIONAL"

    elif quality >= 80:

        signal = "HIGH"

    elif quality >= 65:

        signal = "GOOD"

    elif quality >= 50:

        signal = "MODERATE"

    else:

        signal = "LOW"

    return {

        "signal": signal,

        "quality": quality,

        "confidence": round(
            avg_confidence,
            2,
        ),

        "reason": (

            f"{strong_modules}/{active} "

            f"engines above 80% confidence"

        ),

        "metrics": {

            "ActiveModules": active,

            "AverageConfidence": round(
                avg_confidence,
                2,
            ),

            "BullScore": bullish,

            "BearScore": bearish,

            "AgreementScore": agreement,

            "StrongModules": strong_modules,

            "DecisionQuality": quality,

        },

    }
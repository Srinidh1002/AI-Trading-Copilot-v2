"""
Self Validation Engine

Validates the final trade decision by comparing
signals from all major institutional engines.
"""


def analyze_self_validation(snapshot):

    engines = {

        "Trend": snapshot.get("trend_analysis", {}),
        "Structure": snapshot.get("structure_analysis", {}),
        "Candlestick": snapshot.get("candlestick_analysis", {}),
        "Volume": snapshot.get("volume_analysis", {}),
        "Market Breadth": snapshot.get("market_breadth_analysis", {}),
        "Market Regime": snapshot.get("market_regime_analysis", {}),
        "Liquidity": snapshot.get("liquidity_analysis", {}),
        "Correlation": snapshot.get("correlation_analysis", {}),
        "FII/DII": snapshot.get("fii_dii_analysis", {}),
        "VIX": snapshot.get("vix_analysis", {}),
        "News": snapshot.get("news_analysis", {}),
        "Economic": snapshot.get("economic_analysis", {}),
        "Market Strength": snapshot.get("market_strength_analysis", {}),
        "Execution": snapshot.get("execution_quality_analysis", {}),
        "Portfolio": snapshot.get("portfolio_risk_analysis", {}),
        "Confluence": snapshot.get("confluence_analysis", {}),
    }

    bullish = 0
    bearish = 0
    neutral = 0

    confidence_sum = 0

    active = 0

    confirmations = []
    conflicts = []

    bullish_signals = {

        "BUY",
        "BULLISH",
        "VERY_BULLISH",
        "TRENDING_BULLISH",
        "LOW_RISK",
        "EXCELLENT",
        "STRONG_BUY",

    }

    bearish_signals = {

        "SELL",
        "BEARISH",
        "VERY_BEARISH",
        "TRENDING_BEARISH",
        "HIGH_RISK",
        "POOR",
        "STRONG_SELL",

    }

    for name, engine in engines.items():

        if not engine:
            continue

        active += 1

        signal = str(

            engine.get(
                "signal",
                "UNKNOWN",
            )

        ).upper()

        confidence_sum += engine.get(
            "confidence",
            0,
        )

        if signal in bullish_signals:

            bullish += 1

            confirmations.append(name)

        elif signal in bearish_signals:

            bearish += 1

            conflicts.append(name)

        else:

            neutral += 1

    if active == 0:

        return {

            "status": "UNKNOWN",

            "agreement": 0,

            "confidence": 0,

            "reason": "No engines available",

            "metrics": {},

        }

    dominant = max(

        bullish,

        bearish,

        neutral,

    )

    agreement = round(

        dominant

        * 100

        / active,

        2,

    )

    if agreement >= 90:

        status = "VERY_HIGH"

    elif agreement >= 75:

        status = "HIGH"

    elif agreement >= 60:

        status = "MEDIUM"

    else:

        status = "LOW"

    return {

        "status": status,

        "agreement": agreement,

        "confidence": round(

            confidence_sum / active,

            2,

        ),

        "reason": (

            f"{bullish} Bullish | "

            f"{bearish} Bearish | "

            f"{neutral} Neutral"

        ),

        "metrics": {

            "ActiveEngines": active,

            "BullishVotes": bullish,

            "BearishVotes": bearish,

            "NeutralVotes": neutral,

            "Confirmations": confirmations,

            "Conflicts": conflicts,

        },

    }
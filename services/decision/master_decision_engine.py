"""
Master Decision Engine

Institutional Decision Engine V5
"""
# TODO(V1): Replace archive dependency with active analysis module.
from archive.market_structure_engine import (
    analyze_market_structure,
)

# TODO(V1): Replace archive dependency with active analysis module.
from archive.smart_money_engine import (
    analyze_smart_money,
)
from services.analysis.trend_engine import analyze_trend
from archive.market_structure_engine import (
    analyze_market_structure,
)
from services.analysis.candlestick_engine import (
    analyze_candlestick,
)
from services.analysis.support_resistance_engine import (
    analyze_support_resistance,
)
from archive.smart_money_engine import (
    analyze_smart_money,
)
from services.analysis.volume_engine import (
    analyze_volume,
)
from services.analysis.fii_dii_engine import (
    analyze_fii_dii,
)
from services.analysis.vix_engine import (
    analyze_vix,
)
from services.market.live_multi_timeframe_engine import (
    LiveMultiTimeframeEngine,
)
from services.core.constants import (
    EXCHANGE,
    SYMBOL_TOKEN,
)

DECISION_THRESHOLD = 2.0

MTF_ENGINE = LiveMultiTimeframeEngine()


def make_decision(snapshot):

    trend = analyze_trend(snapshot)

    structure = analyze_market_structure(snapshot)

    candle = analyze_candlestick(snapshot)

    levels = analyze_support_resistance(snapshot)

    smart_money = analyze_smart_money(snapshot)

    volume = analyze_volume(snapshot)

    fii_dii = analyze_fii_dii(snapshot)

    vix = analyze_vix(snapshot)

    try:

        mtf = MTF_ENGINE.analyze(
            EXCHANGE,
            SYMBOL_TOKEN,
        )

    except Exception:

        mtf = {

            "Bias": "Neutral",

            "Confidence": 0,

            "BullScore": 0,

            "BearScore": 0,

            "Confirmations": [],

        }

    option_analysis = snapshot.get(
        "option_analysis",
        {},
    )

    pcr = option_analysis.get("PCR", {})

    oi = option_analysis.get("OI", {})

    flow = option_analysis.get("Flow", {})

    oi_change = option_analysis.get("OIChange", {})

    greeks = option_analysis.get("Greeks", {})

    max_pain = option_analysis.get("MaxPain", {})

    bull = 0.0

    bear = 0.0

    reasons = []

    # ----------------------------------
    # Institutional Voting Matrix
    # ----------------------------------

    votes = []

    # --------------------------------------------------
    # Trend
    # --------------------------------------------------

    bull += trend["bull_score"]

    bear += trend["bear_score"]

    # ----------------------------------
    # Institutional Vote
    # ----------------------------------

    if trend["bull_score"] > trend["bear_score"]:

        votes.append(
            {
                "Engine": "Trend",
                "Vote": "Bullish",
                "Weight": trend["bull_score"],
            }
        )

    elif trend["bear_score"] > trend["bull_score"]:

        votes.append(
            {
                "Engine": "Trend",
                "Vote": "Bearish",
                "Weight": trend["bear_score"],
            }
        )

    else:

        votes.append(
            {
                "Engine": "Trend",
                "Vote": "Neutral",
                "Weight": 0,
            }
        )

    if trend["reason"]:

        reasons.append(
            trend["reason"]
        )
    # --------------------------------------------------
    # Market Structure
    # --------------------------------------------------

    if structure["signal"] == "UPTREND":

        bull += 2

        votes.append(
            {
                "Engine": "Market Structure",
                "Vote": "Bullish",
                "Weight": 2,
            }
        )

        reasons.append(
            structure["reason"]
        )

    elif structure["signal"] == "DOWNTREND":

        bear += 2

        votes.append(
            {
                "Engine": "Market Structure",
                "Vote": "Bearish",
                "Weight": 2,
            }
        )

        reasons.append(
            structure["reason"]
        )

    else:

        votes.append(
            {
                "Engine": "Market Structure",
                "Vote": "Neutral",
                "Weight": 0,
            }
        )

    # --------------------------------------------------
    # Candlestick
    # --------------------------------------------------

    if candle["signal"] == "BULLISH":

        bull += 1.5

        votes.append(
            {
                "Engine": "Candlestick",
                "Vote": "Bullish",
                "Weight": 1.5,
            }
        )

        reasons.append(
            candle["reason"]
        )

    elif candle["signal"] == "BEARISH":

        bear += 1.5

        votes.append(
            {
                "Engine": "Candlestick",
                "Vote": "Bearish",
                "Weight": 1.5,
            }
        )

        reasons.append(
            candle["reason"]
        )

    else:

        votes.append(
            {
                "Engine": "Candlestick",
                "Vote": "Neutral",
                "Weight": 0,
            }
        )
    # --------------------------------------------------
    # Volume
    # --------------------------------------------------

    bull += volume["bull_score"]

    bear += volume["bear_score"]

    # ----------------------------------
    # Institutional Vote
    # ----------------------------------

    if volume["bull_score"] > volume["bear_score"]:

        votes.append(
            {
                "Engine": "Volume",
                "Vote": "Bullish",
                "Weight": volume["bull_score"],
            }
        )

    elif volume["bear_score"] > volume["bull_score"]:

        votes.append(
            {
                "Engine": "Volume",
                "Vote": "Bearish",
                "Weight": volume["bear_score"],
            }
        )

    else:

        votes.append(
            {
                "Engine": "Volume",
                "Vote": "Neutral",
                "Weight": 0,
            }
        )

    if volume["reason"]:

        reasons.append(
            volume["reason"]
        )

    # --------------------------------------------------
    # FII / DII
    # --------------------------------------------------

    bull += fii_dii["bull_score"]

    bear += fii_dii["bear_score"]

    if fii_dii["reason"]:

        reasons.append(
            fii_dii["reason"]
        )

    # --------------------------------------------------
    # India VIX
    # --------------------------------------------------

    bull += vix["bull_score"]

    bear += vix["bear_score"]

    if vix["reason"]:

        reasons.append(
            vix["reason"]
        )

    # --------------------------------------------------
    # Smart Money
    # --------------------------------------------------

    confidence_bonus = 0

    if smart_money["signal"] == "STRONG":

        confidence_bonus = 10

        votes.append(
            {
                "Engine": "Smart Money",
                "Vote": "Bullish",
                "Weight": 4,
            }
        )

        reasons.append(
            smart_money["reason"]
        )

    elif smart_money["signal"] == "MODERATE":

        confidence_bonus = 5

        votes.append(
            {
                "Engine": "Smart Money",
                "Vote": "Bullish",
                "Weight": 2,
            }
        )

    else:

        votes.append(
            {
                "Engine": "Smart Money",
                "Vote": "Neutral",
                "Weight": 0,
            }
        )

    # --------------------------------------------------
    # Multi-Timeframe
    # --------------------------------------------------

    if mtf["Bias"] == "Bullish":

        bull += 4

    elif mtf["Bias"] == "Bearish":

        bear += 4

    if mtf["Confirmations"]:

        reasons.extend(
            mtf["Confirmations"]
        )

    # --------------------------------------------------
    # PCR
    # --------------------------------------------------

    if pcr:

        bias = pcr.get("Bias")

        if bias == "Strong Bullish":

            bull += 3

        elif bias == "Bullish":

            bull += 2

        elif bias == "Strong Bearish":

            bear += 3

        elif bias == "Bearish":

            bear += 2

        if bias:

            reasons.append(
                f"PCR {bias}"
            )
        # --------------------------------------------------
    # Open Interest
    # --------------------------------------------------

    if oi:

        bias = oi.get("Bias")

        if bias == "Bullish":

            bull += 3

        elif bias == "Bearish":

            bear += 3

        if bias:

            reasons.append(
                f"OI {bias}"
            )

    # --------------------------------------------------
    # Option Flow
    # --------------------------------------------------

    if flow:

        bias = flow.get("Bias")

        if bias == "Strong Bullish":

            bull += 4

        elif bias == "Bullish":

            bull += 3

        elif bias == "Strong Bearish":

            bear += 4

        elif bias == "Bearish":

            bear += 3

        if flow.get("Flow"):

            reasons.append(
                flow["Flow"]
            )

    # --------------------------------------------------
    # OI Change
    # --------------------------------------------------

    if oi_change:

        summary = oi_change.get(
            "Summary",
            {},
        )

        bull += summary.get(
            "BullScore",
            0,
        )

        bear += summary.get(
            "BearScore",
            0,
        )

        if summary.get("Bias"):

            reasons.append(
                summary["Bias"]
            )

    # --------------------------------------------------
    # Greeks
    # --------------------------------------------------

    if greeks:

        summary = greeks.get(
            "Summary",
            {},
        )

        bias = summary.get(
            "Bias",
            "Neutral",
        )

        if bias == "Bullish":

            bull += 3

        elif bias == "Bearish":

            bear += 3

        reasons.append(
            f"Greeks {bias}"
        )

    # --------------------------------------------------
    # Max Pain
    # --------------------------------------------------

    if max_pain:

        reasons.append(
            f"Max Pain {max_pain.get('MaxPain')}"
        )

    # --------------------------------------------------
    # Final Signal
    # --------------------------------------------------

    difference = bull - bear

    if difference >= DECISION_THRESHOLD:

        signal = "BUY"

    elif difference <= -DECISION_THRESHOLD:

        signal = "SELL"

    else:

        signal = "HOLD"

    # --------------------------------------------------
    # Support / Resistance Filter
    # --------------------------------------------------

    if signal == "BUY":

        if levels["signal"] == "RESISTANCE":

            signal = "HOLD"

            reasons.append(
                levels["reason"]
            )

    elif signal == "SELL":

        if levels["signal"] == "SUPPORT":

            signal = "HOLD"

            reasons.append(
                levels["reason"]
            )

    # --------------------------------------------------
    # Confidence
    # --------------------------------------------------

    confidence_inputs = [
        trend["confidence"],
        structure["confidence"],
        candle["confidence"],
        volume["confidence"],
        fii_dii["confidence"],
        vix["confidence"],
    ]

    confidence = (
        sum(confidence_inputs) / len(confidence_inputs)
    ) + confidence_bonus

    for engine in (

        pcr,

        oi,

        flow,

        greeks.get(
            "Summary",
            {},
        ),

        {
            "Confidence": mtf["Confidence"],
        },

    ):

        if engine:

            confidence += (

                engine.get(
                    "Confidence",
                    50,
                ) - 50

            ) / 8

    confidence = round(

        max(
            0,
            min(
                confidence,
                100,
            ),
        ),

        2,

    )

    if not reasons:

        reasons.append(
            "No confirmation"
        )
    return {

    # ==============================
    # CORE DECISION CONTRACT
    # ==============================

    "signal": signal,
    "confidence": confidence,
    "reason": ", ".join(dict.fromkeys(reasons)),

    # ==============================
    # SCORES
    # ==============================

    "bull_score": round(bull, 2),
    "bear_score": round(bear, 2),

    # ==============================
    # TECHNICAL LEVELS
    # ==============================

    "support": levels["support"],
    "resistance": levels["resistance"],

    # ==============================
    # OPTION DATA
    # ==============================

    "option_bias": flow.get(
        "Bias",
        oi.get("Bias", "Neutral"),
    ),

    "option_flow": flow.get(
        "Flow",
        "Unknown",
    ),

    "greeks_bias": greeks.get(
        "Summary",
        {},
    ).get(
        "Bias",
        "Neutral",
    ),

    "pcr": pcr.get("PCR"),

    "max_pain": max_pain.get("MaxPain"),

    "option_support": max_pain.get("Support"),

    "option_resistance": max_pain.get("Resistance"),

    # ==============================
    # MULTI TIMEFRAME
    # ==============================

    "multi_timeframe": {
        "bias": mtf["Bias"],
        "confidence": mtf["Confidence"],
        "confirmations": mtf["Confirmations"],
    },

    # ==============================
    # ANALYSIS ENGINES
    # ==============================

    "trend": trend,
    "market_structure": structure,
    "candlestick": candle,
    "volume": volume,
    "fii_dii": fii_dii,
    "vix": vix,
    "smart_money": smart_money,

    # ==============================
    # VOTES
    # ==============================

    "votes": votes,
}
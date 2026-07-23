"""
Live Multi-Timeframe Engine

Institutional multi-timeframe confirmation engine.
"""

from services.market.market_data_manager import (
    market_data_manager,
)

from services.indicators.indicator_engine import (
    calculate_indicators,
)

from services.analysis.trend_engine import (
    analyze_trend,
)

from archive.market_structure_engine import (
    analyze_market_structure,
)


TIMEFRAMES = (
    "5m",
    "15m",
    "1h",
    "1d",
)

TIMEFRAME_WEIGHT = {
    "5m": 1,
    "15m": 2,
    "1h": 3,
    "1d": 4,
}


class LiveMultiTimeframeEngine:

    def analyze(
        self,
        exchange,
        symboltoken,
    ):

        frames = market_data_manager.get_multiple(
            exchange=exchange,
            symboltoken=symboltoken,
            timeframes=TIMEFRAMES,
        )

        result = {}

        bull = 0
        bear = 0

        confirmations = []

        for timeframe, df in frames.items():

            if df is None or df.empty:
                continue

            snapshot = {
                "history": df,
                "indicators": calculate_indicators(df),
            }

            trend = analyze_trend(snapshot)

            structure = analyze_market_structure(
                snapshot
            )

            weight = TIMEFRAME_WEIGHT[
                timeframe
            ]

            if trend["bull_score"] > trend["bear_score"]:

                bull += weight

                confirmations.append(
                    f"{timeframe} Bullish"
                )

            elif trend["bear_score"] > trend["bull_score"]:

                bear += weight

                confirmations.append(
                    f"{timeframe} Bearish"
                )

            if structure["signal"] == "UPTREND":
                bull += weight

            elif structure["signal"] == "DOWNTREND":
                bear += weight

            result[timeframe] = {
                "Trend": trend,
                "Structure": structure,
            }

        if bull > bear:
            bias = "Bullish"
        elif bear > bull:
            bias = "Bearish"
        else:
            bias = "Neutral"

        total = bull + bear

        confidence = (
            round(
                max(bull, bear)
                / total
                * 100,
                2,
            )
            if total
            else 0
        )

        return {
            "Frames": result,
            "BullScore": bull,
            "BearScore": bear,
            "Bias": bias,
            "Confidence": confidence,
            "Confirmations": confirmations,
        }
"""
Price Market Structure Engine

Detects:

- Higher High (HH)
- Higher Low (HL)
- Lower High (LH)
- Lower Low (LL)
- Swing High
- Swing Low
- Trend
- Structure Strength
"""

from __future__ import annotations

import pandas as pd


SWING_LOOKBACK = 2


class PriceMarketStructureEngine:

    @staticmethod
    def analyze(snapshot):

        history = snapshot.get("history")

        if history is None or len(history) < 30:

            return {

                "trend": "UNKNOWN",

                "structure": "UNKNOWN",

                "confidence": 0,

                "swing_highs": [],

                "swing_lows": [],

            }

        df = history.copy()

        highs = df["high"].astype(float).reset_index(drop=True)

        lows = df["low"].astype(float).reset_index(drop=True)

        swing_highs = []
        swing_lows = []

        for i in range(
            SWING_LOOKBACK,
            len(df) - SWING_LOOKBACK,
        ):

            high = highs.iloc[i]
            low = lows.iloc[i]

            if high == max(
                highs.iloc[
                    i - SWING_LOOKBACK:
                    i + SWING_LOOKBACK + 1
                ]
            ):

                swing_highs.append(
                    (i, float(high))
                )

            if low == min(
                lows.iloc[
                    i - SWING_LOOKBACK:
                    i + SWING_LOOKBACK + 1
                ]
            ):

                swing_lows.append(
                    (i, float(low))
                )

        if len(swing_highs) < 2 or len(swing_lows) < 2:

            return {

                "trend": "UNKNOWN",

                "structure": "UNKNOWN",

                "confidence": 20,

                "swing_highs": swing_highs,

                "swing_lows": swing_lows,

            }

        last_high = swing_highs[-1][1]
        prev_high = swing_highs[-2][1]

        last_low = swing_lows[-1][1]
        prev_low = swing_lows[-2][1]

        hh = last_high > prev_high
        hl = last_low > prev_low

        lh = last_high < prev_high
        ll = last_low < prev_low

        if hh and hl:

            trend = "BULLISH"
            structure = "HH-HL"
            confidence = 90

        elif lh and ll:

            trend = "BEARISH"
            structure = "LH-LL"
            confidence = 90

        elif hh and ll:

            trend = "TRANSITION"
            structure = "HH-LL"
            confidence = 60

        elif lh and hl:

            trend = "TRANSITION"
            structure = "LH-HL"
            confidence = 60

        else:

            trend = "RANGE"
            structure = "SIDEWAYS"
            confidence = 40

        return {

            "trend": trend,

            "structure": structure,

            "confidence": confidence,

            "higher_high": hh,

            "higher_low": hl,

            "lower_high": lh,

            "lower_low": ll,

            "last_swing_high": last_high,

            "last_swing_low": last_low,

            "previous_swing_high": prev_high,

            "previous_swing_low": prev_low,

            "swing_highs": swing_highs,

            "swing_lows": swing_lows,

        }
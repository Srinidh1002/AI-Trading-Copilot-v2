"""
Institutional Volume Engine

Analyzes volume behaviour for institutional confirmation.
"""

import math

import pandas as pd


RVOL_LOOKBACK = 20
SPIKE_MULTIPLIER = 1.5


def analyze_volume(snapshot):

    history = snapshot.get("history")

    if history is None or len(history) < RVOL_LOOKBACK:

        return {

            "signal": "NEUTRAL",

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "reason": "Insufficient volume history",

            "metrics": {},

        }

    df = history.copy()

    required_columns = [
        "volume",
        "close",
        "high",
        "low",
    ]

    for column in required_columns:

        if column not in df.columns:

            return {

                "signal": "NEUTRAL",

                "bull_score": 0,

                "bear_score": 0,

                "confidence": 0,

                "reason": f"Missing column: {column}",

                "metrics": {},

            }

    df = df[required_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )

    df = df.dropna()

    if len(df) < RVOL_LOOKBACK:

        return {

            "signal": "NEUTRAL",

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "reason": "Insufficient valid volume history",

            "metrics": {},

        }

    volume = df["volume"]
    close = df["close"]
    high = df["high"]
    low = df["low"]

    latest_volume = float(volume.iloc[-1])

    average_volume = float(
        volume.tail(RVOL_LOOKBACK).mean()
    )

    if average_volume <= 0:

        rvol = 0.0

    else:

        rvol = latest_volume / average_volume

    volume_spike = rvol >= SPIKE_MULTIPLIER

    typical_price = (high + low + close) / 3

    cumulative_volume = volume.cumsum()

    cumulative_pv = (
        typical_price * volume
    ).cumsum()

    total_volume = float(
        cumulative_volume.iloc[-1]
    )

    if total_volume <= 0 or math.isnan(total_volume):

        vwap = float(close.iloc[-1])

    else:

        vwap = float(
            cumulative_pv.iloc[-1]
            / total_volume
        )

    latest_close = float(close.iloc[-1])

    bull = 0
    bear = 0

    reasons = []

    # --------------------------------------------------
    # Relative Volume
    # --------------------------------------------------

    if rvol >= 2:

        bull += 3

        reasons.append(
            "Very High Relative Volume"
        )

    elif rvol >= 1.5:

        bull += 2

        reasons.append(
            "High Relative Volume"
        )

    elif rvol < 0.8:

        bear += 1

        reasons.append(
            "Low Relative Volume"
        )

    # --------------------------------------------------
    # VWAP
    # --------------------------------------------------

    if latest_close > vwap:

        bull += 2

        reasons.append(
            "Trading Above VWAP"
        )

    elif latest_close < vwap:

        bear += 2

        reasons.append(
            "Trading Below VWAP"
        )

    # --------------------------------------------------
    # Accumulation / Distribution
    # --------------------------------------------------

    if volume_spike:

        if latest_close > float(close.iloc[-2]):

            bull += 3

            reasons.append(
                "Institutional Accumulation"
            )

        elif latest_close < float(close.iloc[-2]):

            bear += 3

            reasons.append(
                "Institutional Distribution"
            )

    # --------------------------------------------------
    # Volume Trend
    # --------------------------------------------------

    recent_avg = float(
        volume.tail(5).mean()
    )

    previous_avg = float(
        volume.tail(10).head(5).mean()
    )

    if recent_avg > previous_avg:

        bull += 1

        reasons.append(
            "Increasing Volume Trend"
        )

    elif recent_avg < previous_avg:

        bear += 1

        reasons.append(
            "Decreasing Volume Trend"
        )

    # --------------------------------------------------
    # Final Signal
    # --------------------------------------------------

    if bull >= bear + 2:

        signal = "BULLISH"

    elif bear >= bull + 2:

        signal = "BEARISH"

    else:

        signal = "NEUTRAL"

    dominance = abs(
        bull - bear
    )

    confidence = min(

        100,

        round(

            (dominance * 15)

            + min(
                rvol * 20,
                40,
            ),

            2,

        ),

    )

    return {

        "signal": signal,

        "bull_score": bull,

        "bear_score": bear,

        "confidence": confidence,

        "reason": ", ".join(reasons),

        "metrics": {

            "RVOL": round(rvol, 2),

            "VWAP": round(vwap, 2),

            "LatestVolume": int(latest_volume),

            "AverageVolume": int(average_volume),

            "VolumeSpike": volume_spike,

        },

    }
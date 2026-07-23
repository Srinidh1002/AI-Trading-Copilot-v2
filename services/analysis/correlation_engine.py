"""
Correlation Engine

Measures correlation between the current symbol
and benchmark indices.
"""

from typing import List
import numpy as np


def _returns(prices: List[float]):

    if len(prices) < 2:
        return np.array([])

    prices = np.array(prices, dtype=float)

    return np.diff(prices) / prices[:-1]


def analyze_correlation(snapshot):

    """
    Expected snapshot

    snapshot["correlation"] = {

        "symbol": [...],
        "nifty": [...],
        "banknifty": [...],
        "sensex": [...]

    }
    """

    data = snapshot.get(
        "correlation",
        {},
    )

    symbol = data.get(
        "symbol",
        [],
    )

    if len(symbol) < 20:

        return {

            "signal": "UNKNOWN",

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "reason": "Correlation data unavailable",

            "metrics": {},

        }

    symbol_ret = _returns(symbol)

    metrics = {}

    reasons = []

    bull = 0
    bear = 0

    confidence = 50

    for benchmark in [

        "nifty",
        "banknifty",
        "sensex",

    ]:

        bench = data.get(
            benchmark,
            [],
        )

        if len(bench) != len(symbol):

            continue

        bench_ret = _returns(bench)

        if len(bench_ret) != len(symbol_ret):

            continue

        corr = float(

            np.corrcoef(
                symbol_ret,
                bench_ret,
            )[0][1]

        )

        metrics[benchmark.upper()] = round(
            corr,
            3,
        )

        if corr >= 0.80:

            bull += 2

            reasons.append(
                f"Strong {benchmark.upper()} Correlation"
            )

        elif corr <= -0.50:

            bear += 2

            reasons.append(
                f"Inverse {benchmark.upper()} Correlation"
            )

    if bull >= bear + 2:

        signal = "BULLISH"

    elif bear >= bull + 2:

        signal = "BEARISH"

    else:

        signal = "NEUTRAL"

    confidence += abs(
        bull - bear
    ) * 8

    confidence = min(
        confidence,
        100,
    )

    return {

        "signal": signal,

        "bull_score": bull,

        "bear_score": bear,

        "confidence": round(
            confidence,
            2,
        ),

        "reason": ", ".join(reasons),

        "metrics": metrics,

    }
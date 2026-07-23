"""
Execution Quality Engine

Evaluates execution quality using slippage,
spread, fill percentage and execution latency.
"""


def analyze_execution_quality(snapshot):

    """
    Expected snapshot:

    snapshot["execution"] = {

        "expected_price": float,

        "executed_price": float,

        "spread": float,

        "fill_percent": float,

        "latency_ms": float,

    }
    """

    execution = snapshot.get(
        "execution",
        {},
    )

    expected = float(
        execution.get(
            "expected_price",
            0,
        )
    )

    executed = float(
        execution.get(
            "executed_price",
            0,
        )
    )

    spread = float(
        execution.get(
            "spread",
            0,
        )
    )

    fill = float(
        execution.get(
            "fill_percent",
            100,
        )
    )

    latency = float(
        execution.get(
            "latency_ms",
            0,
        )
    )

    if expected <= 0:

        return {

            "signal": "UNKNOWN",

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "reason": "Execution data unavailable",

            "metrics": {},

        }

    slippage = abs(
        executed - expected
    )

    slippage_pct = (

        slippage / expected

    ) * 100

    bull = 0
    bear = 0

    reasons = []

    # ------------------------
    # Slippage
    # ------------------------

    if slippage_pct <= 0.02:

        bull += 3

        reasons.append(
            "Minimal Slippage"
        )

    elif slippage_pct <= 0.05:

        bull += 2

        reasons.append(
            "Low Slippage"
        )

    else:

        bear += 3

        reasons.append(
            "High Slippage"
        )

    # ------------------------
    # Spread
    # ------------------------

    if spread <= 0.05:

        bull += 2

        reasons.append(
            "Tight Spread"
        )

    elif spread > 0.25:

        bear += 2

        reasons.append(
            "Wide Spread"
        )

    # ------------------------
    # Fill Rate
    # ------------------------

    if fill >= 99:

        bull += 2

        reasons.append(
            "Complete Fill"
        )

    elif fill < 95:

        bear += 2

        reasons.append(
            "Partial Fill"
        )

    # ------------------------
    # Latency
    # ------------------------

    if latency <= 100:

        bull += 2

        reasons.append(
            "Fast Execution"
        )

    elif latency >= 500:

        bear += 2

        reasons.append(
            "Slow Execution"
        )

    # ------------------------

    if bull >= bear + 2:

        signal = "EXCELLENT"

    elif bear >= bull + 2:

        signal = "POOR"

    else:

        signal = "AVERAGE"

    confidence = min(

        100,

        round(

            60

            + abs(
                bull - bear
            ) * 6,

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

            "ExpectedPrice": expected,

            "ExecutedPrice": executed,

            "Slippage": round(
                slippage,
                4,
            ),

            "SlippagePercent": round(
                slippage_pct,
                4,
            ),

            "Spread": spread,

            "FillPercent": fill,

            "LatencyMS": latency,

        },

    }
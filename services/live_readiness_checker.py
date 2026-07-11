"""
Live pipeline readiness checker.

Validates multi-timeframe data before the analysis pipeline runs.
This module is read-only.
"""


MINIMUM_CANDLES = {
    "5m": 200,
    "15m": 200,
    "1h": 100,
    "1d": 100,
}


def check_live_readiness(timeframes):
    if not timeframes:
        raise ValueError(
            "No timeframe data provided."
        )

    checks = {}
    ready = True
    reasons = []

    for timeframe, minimum in MINIMUM_CANDLES.items():
        data = timeframes.get(timeframe)

        if data is None:
            checks[timeframe] = {
                "ready": False,
                "candles": 0,
                "minimum": minimum,
            }

            reasons.append(
                f"{timeframe} timeframe is missing."
            )

            ready = False
            continue

        candle_count = len(data)

        timeframe_ready = (
            candle_count >= minimum
        )

        checks[timeframe] = {
            "ready": timeframe_ready,
            "candles": candle_count,
            "minimum": minimum,
        }

        if not timeframe_ready:
            ready = False

            reasons.append(
                f"{timeframe} has only "
                f"{candle_count} candles; "
                f"minimum required is {minimum}."
            )

    return {
        "ready": ready,
        "checks": checks,
        "reasons": reasons,
    }
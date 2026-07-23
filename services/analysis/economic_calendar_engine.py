"""
Economic Calendar Engine

Institutional macro event analysis.
"""


HIGH_IMPACT = {

    "RBI",
    "FED",
    "FOMC",
    "CPI",
    "WPI",
    "GDP",
    "NFP",
    "INFLATION",
    "UNEMPLOYMENT",
    "PMI",
    "INTEREST RATE",

}


def analyze_economic_calendar(snapshot):

    """
    Expected snapshot:

    snapshot["economic_events"] = [

        {
            "event": "...",
            "impact": "High",
            "actual": "...",
            "forecast": "...",
            "previous": "...",
        }

    ]
    """

    events = snapshot.get(
        "economic_events",
        [],
    )

    if not events:

        return {

            "signal": "UNKNOWN",

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "reason": "No economic events",

            "metrics": {},

        }

    bull = 0
    bear = 0

    high_events = 0

    reasons = []

    for event in events:

        name = event.get(
            "event",
            "",
        ).upper()

        impact = event.get(
            "impact",
            "",
        ).upper()

        if impact == "HIGH":

            high_events += 1

            bear += 1

            reasons.append(
                f"High Impact: {name}"
            )

        for keyword in HIGH_IMPACT:

            if keyword in name:

                bear += 1

                break

    if high_events == 0:

        bull += 2

        reasons.append(
            "No major macro events"
        )

    if bull >= bear + 2:

        signal = "BULLISH"

    elif bear >= bull + 2:

        signal = "BEARISH"

    else:

        signal = "NEUTRAL"

    confidence = min(

        100,

        round(

            45

            + high_events * 10,

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

            "HighImpactEvents": high_events,

            "TotalEvents": len(events),

        },

    }
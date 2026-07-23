"""
Change Of Character Engine
"""


def detect_choch(swings):

    trend = swings["trend"]

    return {
        "choch": trend == "Neutral"
    }
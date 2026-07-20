"""
Liquidity Sweep Engine
"""


def detect_liquidity(df, swings):

    close = float(df["close"].iloc[-1])

    high = swings["last_swing_high"]
    low = swings["last_swing_low"]

    status = "Inside Range"

    if high and close > high:
        status = "Above High"

    elif low and close < low:
        status = "Below Low"

    return {
        "liquidity": status
    }
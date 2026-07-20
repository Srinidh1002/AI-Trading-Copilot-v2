"""
Break Of Structure Engine
"""


def detect_bos(df, swings):

    close = float(df["close"].iloc[-1])

    last_high = swings["last_swing_high"]
    last_low = swings["last_swing_low"]

    bos = False
    direction = "None"

    if last_high and close > last_high:
        bos = True
        direction = "Bullish"

    elif last_low and close < last_low:
        bos = True
        direction = "Bearish"

    return {
        "bos": bos,
        "direction": direction,
    }
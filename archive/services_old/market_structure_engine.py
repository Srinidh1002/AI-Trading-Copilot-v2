"""
Market Structure Engine V1
"""


def analyze_market_structure(snapshot):

    history = snapshot["history"].copy()

    high = history["high"]
    low = history["low"]

    last_high = high.iloc[-1]
    prev_high = high.iloc[-2]

    last_low = low.iloc[-1]
    prev_low = low.iloc[-2]

    if last_high > prev_high and last_low > prev_low:
        structure = "Higher High Higher Low"

    elif last_high < prev_high and last_low < prev_low:
        structure = "Lower High Lower Low"

    elif last_high > prev_high:
        structure = "Higher High"

    elif last_low < prev_low:
        structure = "Lower Low"

    else:
        structure = "Range"

    return {
        "structure": structure,
        "last_high": round(last_high, 2),
        "previous_high": round(prev_high, 2),
        "last_low": round(last_low, 2),
        "previous_low": round(prev_low, 2),
    }
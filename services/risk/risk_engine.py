"""
Risk Engine

Calculates Stop Loss, Target and Risk/Reward.
"""


def calculate_risk(snapshot, decision):
    """
    Calculate trade risk parameters.

    Returns
    -------
    dict
    """

    price = snapshot["ltp"]
    atr = snapshot["indicators"]["atr"]["atr"]

    signal = decision["signal"]

    if signal == "BUY":

        stop_loss = price - (1.5 * atr)
        target = price + (3 * atr)

    elif signal == "SELL":

        stop_loss = price + (1.5 * atr)
        target = price - (3 * atr)

    else:

        stop_loss = price
        target = price

    risk = abs(price - stop_loss)
    reward = abs(target - price)

    rr = round(
        reward / risk,
        2,
    ) if risk else 0

    return {
        "entry": round(price, 2),
        "stop_loss": round(stop_loss, 2),
        "target": round(target, 2),
        "risk_reward": rr,
    }
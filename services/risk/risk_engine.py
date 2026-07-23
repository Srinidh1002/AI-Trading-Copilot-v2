"""
Risk Engine

Calculates Stop Loss, Target and Risk/Reward.
"""


def calculate_risk(snapshot, decision):
    """
    Calculate trade risk parameters.
    """

    price = float(snapshot["ltp"])
    atr = float(snapshot["indicators"]["ATR"])

    signal = decision.get("signal", "HOLD")

    atr = max(atr, 1)

    if signal == "BUY":

        stop_loss = price - (1.5 * atr)
        target = price + (3.0 * atr)

    elif signal == "SELL":

        stop_loss = price + (1.5 * atr)
        target = price - (3.0 * atr)

    else:

        return {
            "entry": round(price, 2),
            "stop_loss": round(price, 2),
            "target": round(price, 2),
            "risk": 0.0,
            "reward": 0.0,
            "risk_reward": 0.0,
            "trade_valid": False,
        }

    risk = abs(price - stop_loss)
    reward = abs(target - price)

    rr = round(reward / risk, 2) if risk else 0.0

    return {
        "entry": round(price, 2),
        "stop_loss": round(stop_loss, 2),
        "target": round(target, 2),
        "risk": round(risk, 2),
        "reward": round(reward, 2),
        "risk_reward": rr,
        "trade_valid": rr >= 1.5,
    }
"""
Trade Recommendation Engine
"""


def trade_recommendation(price, decision):

    signal = decision["signal"]
    confidence = decision["confidence"]

    if signal == "BUY":

        entry = round(price, 2)

        stop_loss = round(price * 0.985, 2)

        target1 = round(price * 1.015, 2)

        target2 = round(price * 1.03, 2)

    elif signal == "SELL":

        entry = round(price, 2)

        stop_loss = round(price * 1.015, 2)

        target1 = round(price * 0.985, 2)

        target2 = round(price * 0.97, 2)

    else:

        entry = None
        stop_loss = None
        target1 = None
        target2 = None

    if entry and stop_loss and target1:

        risk = abs(entry - stop_loss)

        reward = abs(target1 - entry)

        rr = round(reward / risk, 2)

    else:

        rr = 0

    return {

        "signal": signal,

        "confidence": confidence,

        "entry": entry,

        "stop_loss": stop_loss,

        "target1": target1,

        "target2": target2,

        "risk_reward": rr,
    }
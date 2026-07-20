"""
Risk Management Engine V2
"""


def calculate_trade_levels(current_price, support, resistance):
    """
    Calculates Entry, Stop Loss,
    Target 1 and Target 2.
    """

    entry = round(current_price, 2)

    risk = abs(current_price - support)

    if risk == 0:
        risk = current_price * 0.005

    stop_loss = round(support, 2)

    target1 = round(resistance, 2)

    target2 = round(current_price + (2 * risk), 2)

    reward = target2 - entry

    rr = round(reward / risk, 2)

    return {
        "ENTRY": entry,
        "STOP_LOSS": stop_loss,
        "TARGET1": target1,
        "TARGET2": target2,
        "RR": rr,
    }
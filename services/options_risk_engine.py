"""
Options-specific risk engine.

Validates:
- Lot-aware position sizing
- Premium exposure
- Bid-ask spread
- Volume and open interest
- Implied volatility
- Delta exposure
- Theta / expiry risk

This module does not place orders.
"""


def evaluate_options_risk(
    capital,
    premium,
    lot_size,
    bid_price,
    ask_price,
    volume,
    open_interest,
    iv,
    delta,
    theta,
    days_to_expiry,
    max_premium_exposure_percent=10.0,
    max_spread_percent=2.0,
    minimum_volume=100,
    minimum_open_interest=500,
    maximum_iv=80.0,
    maximum_lots=5,
):
    reasons = []
    warnings = []

    # -------------------------
    # BASIC VALIDATION
    # -------------------------

    if capital <= 0:
        raise ValueError(
            "Capital must be greater than zero."
        )

    if premium <= 0:
        raise ValueError(
            "Option premium must be greater than zero."
        )

    if lot_size <= 0:
        raise ValueError(
            "Lot size must be greater than zero."
        )

    if bid_price < 0 or ask_price <= 0:
        raise ValueError(
            "Bid and ask prices must be valid."
        )

    if days_to_expiry < 0:
        raise ValueError(
            "Days to expiry cannot be negative."
        )

    # -------------------------
    # BID-ASK SPREAD
    # -------------------------

    midpoint = (
        bid_price + ask_price
    ) / 2

    if midpoint > 0:
        spread_percent = (
            (ask_price - bid_price)
            / midpoint
        ) * 100
    else:
        spread_percent = 100.0

    if spread_percent > max_spread_percent:
        reasons.append(
            "Bid-ask spread exceeds the maximum allowed."
        )

    # -------------------------
    # LIQUIDITY
    # -------------------------

    if volume < minimum_volume:
        reasons.append(
            "Option volume is below the minimum liquidity requirement."
        )

    if open_interest < minimum_open_interest:
        reasons.append(
            "Open interest is below the minimum liquidity requirement."
        )

    # -------------------------
    # IMPLIED VOLATILITY
    # -------------------------

    if iv > maximum_iv:
        warnings.append(
            "Implied volatility is unusually high."
        )

    # -------------------------
    # DELTA
    # -------------------------

    absolute_delta = abs(delta)

    if absolute_delta < 0.20:
        warnings.append(
            "Option delta is very low."
        )

    if absolute_delta > 0.90:
        warnings.append(
            "Option delta is unusually high."
        )

    # -------------------------
    # EXPIRY / THETA RISK
    # -------------------------

    if days_to_expiry == 0:
        reasons.append(
            "Expiry-day trading is blocked by the current risk policy."
        )

    elif days_to_expiry <= 1:
        warnings.append(
            "Option is very close to expiry."
        )

    if theta < -20:
        warnings.append(
            "Option has high negative theta decay."
        )

    # -------------------------
    # PREMIUM EXPOSURE
    # -------------------------

    maximum_premium_exposure = (
        capital
        * max_premium_exposure_percent
        / 100
    )

    cost_per_lot = (
        premium * lot_size
    )

    affordable_lots = int(
        maximum_premium_exposure
        / cost_per_lot
    )

    lots = min(
        affordable_lots,
        maximum_lots,
    )

    quantity = lots * lot_size

    premium_exposure = (
        quantity * premium
    )

    if lots <= 0:
        reasons.append(
            "Capital allocation is insufficient for one option lot."
        )

    # -------------------------
    # FINAL DECISION
    # -------------------------

    approved = len(reasons) == 0

    decision = (
        "APPROVED"
        if approved
        else "REJECTED"
    )

    return {
        "approved": approved,
        "decision": decision,
        "lots": lots,
        "quantity": quantity,
        "premium_exposure": round(
            premium_exposure,
            2,
        ),
        "spread_percent": round(
            spread_percent,
            2,
        ),
        "reasons": reasons,
        "warnings": warnings,
    }
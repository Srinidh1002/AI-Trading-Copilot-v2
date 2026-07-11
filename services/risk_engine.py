"""
Core risk-management engine.

This module does not place orders.
It only approves or rejects a proposed trade.
"""


def evaluate_trade_risk(
    strategy,
    capital,
    entry_price,
    stop_loss,
    target_price,
    daily_pnl=0.0,
    consecutive_losses=0,
    risk_per_trade_percent=1.0,
    max_daily_loss_percent=3.0,
    max_consecutive_losses=3,
    minimum_risk_reward=1.5,
    kill_switch=False,
):
    """
    Evaluate whether a proposed trade satisfies risk rules.
    """

    reasons = []
    warnings = []

    # ---------------------------------
    # BASIC VALIDATION
    # ---------------------------------

    if capital <= 0:
        raise ValueError(
            "Capital must be greater than zero."
        )

    if entry_price <= 0:
        raise ValueError(
            "Entry price must be greater than zero."
        )

    if stop_loss <= 0:
        raise ValueError(
            "Stop loss must be greater than zero."
        )

    if target_price <= 0:
        raise ValueError(
            "Target price must be greater than zero."
        )

    direction = strategy.get(
        "direction",
        "NEUTRAL",
    ).upper()

    strategy_decision = strategy.get(
        "decision",
        "NO_TRADE",
    ).upper()

    # ---------------------------------
    # STRATEGY VETO
    # ---------------------------------

    if strategy_decision != "TRADE":
        reasons.append(
            "Strategy engine did not approve a trade."
        )

    if direction not in {
        "BULLISH",
        "BEARISH",
    }:
        reasons.append(
            "Trade direction is not valid."
        )

    # ---------------------------------
    # EMERGENCY KILL SWITCH
    # ---------------------------------

    if kill_switch:
        reasons.append(
            "Emergency kill switch is active."
        )

    # ---------------------------------
    # DAILY LOSS LIMIT
    # ---------------------------------

    maximum_daily_loss = (
        capital
        * max_daily_loss_percent
        / 100
    )

    if daily_pnl <= -maximum_daily_loss:
        reasons.append(
            "Maximum daily loss limit reached."
        )

    # ---------------------------------
    # CONSECUTIVE LOSS LIMIT
    # ---------------------------------

    if (
        consecutive_losses
        >= max_consecutive_losses
    ):
        reasons.append(
            "Maximum consecutive loss limit reached."
        )

    # ---------------------------------
    # TRADE STRUCTURE
    # ---------------------------------

    if direction == "BULLISH":

        risk_per_unit = (
            entry_price - stop_loss
        )

        reward_per_unit = (
            target_price - entry_price
        )

    elif direction == "BEARISH":

        risk_per_unit = (
            stop_loss - entry_price
        )

        reward_per_unit = (
            entry_price - target_price
        )

    else:
        risk_per_unit = 0
        reward_per_unit = 0

    if risk_per_unit <= 0:
        reasons.append(
            "Stop-loss placement is invalid for trade direction."
        )

    if reward_per_unit <= 0:
        reasons.append(
            "Target placement is invalid for trade direction."
        )

    # ---------------------------------
    # RISK / REWARD
    # ---------------------------------

    if risk_per_unit > 0:
        risk_reward_ratio = (
            reward_per_unit
            / risk_per_unit
        )
    else:
        risk_reward_ratio = 0.0

    if (
        risk_reward_ratio
        < minimum_risk_reward
    ):
        reasons.append(
            "Risk/reward ratio is below the minimum requirement."
        )

    # ---------------------------------
    # POSITION SIZING
    # ---------------------------------

    risk_amount = (
        capital
        * risk_per_trade_percent
        / 100
    )

    if risk_per_unit > 0:
        position_size = int(
            risk_amount
            / risk_per_unit
        )
    else:
        position_size = 0

    if position_size <= 0:
        reasons.append(
            "Calculated position size is zero."
        )

    # ---------------------------------
    # WARNINGS
    # ---------------------------------

    if risk_per_trade_percent > 2:
        warnings.append(
            "Risk per trade is above 2% of capital."
        )

    if risk_reward_ratio < 2:
        warnings.append(
            "Risk/reward ratio is below 2:1."
        )

    # ---------------------------------
    # FINAL DECISION
    # ---------------------------------

    approved = len(reasons) == 0

    decision = (
        "APPROVED"
        if approved
        else "REJECTED"
    )

    return {
        "approved": approved,
        "decision": decision,
        "position_size": position_size,
        "risk_amount": round(
            risk_amount,
            2,
        ),
        "risk_reward_ratio": round(
            risk_reward_ratio,
            2,
        ),
        "reasons": reasons,
        "warnings": warnings,
    }
"""
Core risk-management engine.

Provides:
1. Strategy-level trade risk approval.
2. Lot-based position sizing.

This module does not place orders.
"""

import math


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
    Evaluate whether a proposed trade satisfies
    strategy and account-level risk rules.

    This function is preserved for compatibility
    with the existing trading pipeline.
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

    if not (
        0 < risk_per_trade_percent <= 100
    ):
        raise ValueError(
            "risk_per_trade_percent must be "
            "between 0 and 100."
        )

    if not (
        0 < max_daily_loss_percent <= 100
    ):
        raise ValueError(
            "max_daily_loss_percent must be "
            "between 0 and 100."
        )

    if minimum_risk_reward <= 0:
        raise ValueError(
            "minimum_risk_reward must be "
            "greater than zero."
        )

    direction = str(
        strategy.get(
            "direction",
            "NEUTRAL",
        )
    ).upper()

    strategy_decision = str(
        strategy.get(
            "decision",
            "NO_TRADE",
        )
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
            entry_price
            - stop_loss
        )

        reward_per_unit = (
            target_price
            - entry_price
        )

    elif direction == "BEARISH":

        risk_per_unit = (
            stop_loss
            - entry_price
        )

        reward_per_unit = (
            entry_price
            - target_price
        )

    else:

        risk_per_unit = 0
        reward_per_unit = 0

    if risk_per_unit <= 0:
        reasons.append(
            "Stop-loss placement is invalid "
            "for trade direction."
        )

    if reward_per_unit <= 0:
        reasons.append(
            "Target placement is invalid "
            "for trade direction."
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
            "Risk/reward ratio is below "
            "the minimum requirement."
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

    approved = (
        len(reasons) == 0
    )

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


def calculate_trade_risk(
    capital,
    entry_price,
    stop_loss_price,
    target_price,
    lot_size,
    risk_percent=1.0,
    minimum_risk_reward=1.5,
    maximum_capital_usage_percent=100.0,
):
    """
    Calculate lot-based position sizing for an
    already-approved option trade.

    This function assumes a long option position:
    - Stop loss is below entry.
    - Target is above entry.
    """

    # ---------------------------------
    # INPUT VALIDATION
    # ---------------------------------

    if capital <= 0:
        raise ValueError(
            "capital must be greater than zero."
        )

    if entry_price <= 0:
        raise ValueError(
            "entry_price must be greater than zero."
        )

    if stop_loss_price <= 0:
        raise ValueError(
            "stop_loss_price must be greater than zero."
        )

    if target_price <= 0:
        raise ValueError(
            "target_price must be greater than zero."
        )

    if lot_size <= 0:
        raise ValueError(
            "lot_size must be greater than zero."
        )

    if not (
        0 < risk_percent <= 100
    ):
        raise ValueError(
            "risk_percent must be between 0 and 100."
        )

    if minimum_risk_reward <= 0:
        raise ValueError(
            "minimum_risk_reward must be "
            "greater than zero."
        )

    if not (
        0
        < maximum_capital_usage_percent
        <= 100
    ):
        raise ValueError(
            "maximum_capital_usage_percent "
            "must be between 0 and 100."
        )

    lot_size = int(
        lot_size
    )

    if lot_size <= 0:
        raise ValueError(
            "lot_size must be greater than zero."
        )

    # ---------------------------------
    # LONG OPTION STRUCTURE
    # ---------------------------------

    risk_per_unit = (
        entry_price
        - stop_loss_price
    )

    reward_per_unit = (
        target_price
        - entry_price
    )

    if risk_per_unit == 0:
        raise ValueError(
            "Entry price and stop-loss price "
            "cannot be equal."
        )

    reasons = []

    if risk_per_unit < 0:
        reasons.append(
            "Stop-loss price must be below "
            "entry price for a long option trade."
        )

    if reward_per_unit <= 0:
        reasons.append(
            "Target price must be above "
            "entry price for a long option trade."
        )

    # ---------------------------------
    # RISK BUDGET
    # ---------------------------------

    maximum_risk_amount = (
        capital
        * risk_percent
        / 100
    )

    if risk_per_unit > 0:

        risk_reward_ratio = (
            reward_per_unit
            / risk_per_unit
        )

        risk_per_lot = (
            risk_per_unit
            * lot_size
        )

        lots_by_risk = math.floor(
            maximum_risk_amount
            / risk_per_lot
        )

    else:

        risk_reward_ratio = 0.0
        lots_by_risk = 0

    # ---------------------------------
    # CAPITAL LIMIT
    # ---------------------------------

    usable_capital = (
        capital
        * maximum_capital_usage_percent
        / 100
    )

    capital_per_lot = (
        entry_price
        * lot_size
    )

    lots_by_capital = math.floor(
        usable_capital
        / capital_per_lot
    )

    lots = max(
        0,
        min(
            lots_by_risk,
            lots_by_capital,
        ),
    )

    quantity = (
        lots
        * lot_size
    )

    required_capital = (
        quantity
        * entry_price
    )

    estimated_maximum_loss = (
        quantity
        * max(
            risk_per_unit,
            0,
        )
    )

    # ---------------------------------
    # SAFETY CHECKS
    # ---------------------------------

    if lots_by_risk < 1:
        reasons.append(
            "Risk budget is insufficient "
            "for one complete lot."
        )

    if lots_by_capital < 1:
        reasons.append(
            "Available capital is insufficient "
            "for one complete lot."
        )

    if (
        risk_reward_ratio
        < minimum_risk_reward
    ):
        reasons.append(
            "Risk/reward ratio is below "
            "the minimum requirement."
        )

    if (
        estimated_maximum_loss
        > maximum_risk_amount
    ):
        reasons.append(
            "Estimated maximum loss exceeds "
            "the permitted risk amount."
        )

    allowed = (
        len(reasons) == 0
        and lots >= 1
    )

    decision = (
        "TRADE_ALLOWED"
        if allowed
        else "TRADE_REJECTED"
    )

    if allowed:
        reasons.append(
            "Position size satisfies "
            "capital and risk limits."
        )

    return {
        "allowed": allowed,
        "decision": decision,
        "capital": round(
            capital,
            2,
        ),
        "risk_percent": round(
            risk_percent,
            2,
        ),
        "maximum_risk_amount": round(
            maximum_risk_amount,
            2,
        ),
        "entry_price": round(
            entry_price,
            2,
        ),
        "stop_loss_price": round(
            stop_loss_price,
            2,
        ),
        "target_price": round(
            target_price,
            2,
        ),
        "risk_per_unit": round(
            risk_per_unit,
            2,
        ),
        "reward_per_unit": round(
            reward_per_unit,
            2,
        ),
        "risk_reward_ratio": round(
            risk_reward_ratio,
            2,
        ),
        "lot_size": lot_size,
        "lots": lots,
        "quantity": quantity,
        "required_capital": round(
            required_capital,
            2,
        ),
        "estimated_maximum_loss": round(
            estimated_maximum_loss,
            2,
        ),
        "reasons": reasons,
    }
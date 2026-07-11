"""
Integrated trade-plan engine.

Combines:
- Selected option contract
- Market ATR and structure
- Dynamic stop-loss and target
- Automatic exchange lot size
- Lot-based position sizing
- Final risk authorization

This module does not place orders.
"""

from services.trade_level_engine import (
    calculate_trade_levels,
)

from services.risk_engine import (
    calculate_trade_risk,
)


def _normalize_lot_size(
    raw_lot_size,
):
    """
    Convert a lot-size value into a positive integer.

    Returns zero when the value is missing or invalid.
    """

    try:
        lot_size = int(
            float(
                raw_lot_size
                or 0
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0

    if lot_size <= 0:
        return 0

    return lot_size


def build_trade_plan(
    contract,
    direction,
    spot_price,
    atr,
    capital,
    lot_size=None,
    support=None,
    resistance=None,
    risk_percent=1.0,
    minimum_risk_reward=2.0,
    maximum_capital_usage_percent=100.0,
    option_stop_percent=20.0,
    atr_stop_multiplier=1.0,
):
    """
    Build a complete risk-controlled option trade plan.

    Lot-size priority:
    1. Actual lot size stored in the selected contract.
    2. Manually supplied lot_size fallback.

    This preserves backward compatibility while allowing
    live contracts to use exchange-provided lot sizes.
    """

    # ---------------------------------
    # CONTRACT VALIDATION
    # ---------------------------------

    if not contract:
        return {
            "allowed": False,
            "decision": "TRADE_REJECTED",
            "contract": None,
            "levels": None,
            "risk": None,
            "reasons": [
                "No option contract was provided."
            ],
        }

    if not contract.get(
        "selected",
        False,
    ):
        return {
            "allowed": False,
            "decision": "TRADE_REJECTED",
            "contract": contract,
            "levels": None,
            "risk": None,
            "reasons": [
                "Option contract was not selected."
            ],
        }

    # ---------------------------------
    # DIRECTION VALIDATION
    # ---------------------------------

    direction = str(
        direction
    ).upper()

    if direction not in {
        "BULLISH",
        "BEARISH",
    }:
        raise ValueError(
            "direction must be BULLISH or BEARISH."
        )

    expected_option_type = (
        "CE"
        if direction == "BULLISH"
        else "PE"
    )

    contract_option_type = str(
        contract.get(
            "option_type",
            "",
        )
    ).upper()

    if (
        contract_option_type
        != expected_option_type
    ):
        return {
            "allowed": False,
            "decision": "TRADE_REJECTED",
            "contract": contract,
            "levels": None,
            "risk": None,
            "reasons": [
                "Selected option type does not match "
                "the market direction."
            ],
        }

    # ---------------------------------
    # OPTION PREMIUM
    # ---------------------------------

    option_premium = float(
        contract.get(
            "premium",
            0,
        )
        or 0
    )

    if option_premium <= 0:
        raise ValueError(
            "Selected contract premium must be "
            "greater than zero."
        )

    # ---------------------------------
    # AUTOMATIC LOT SIZE
    # ---------------------------------

    contract_lot_size = (
        _normalize_lot_size(
            contract.get(
                "lot_size",
                0,
            )
        )
    )

    fallback_lot_size = (
        _normalize_lot_size(
            lot_size
        )
    )

    if contract_lot_size > 0:
        resolved_lot_size = (
            contract_lot_size
        )

        lot_size_source = (
            "CONTRACT"
        )

    elif fallback_lot_size > 0:
        resolved_lot_size = (
            fallback_lot_size
        )

        lot_size_source = (
            "MANUAL_FALLBACK"
        )

    else:
        raise ValueError(
            "No valid lot size is available "
            "from the selected contract or fallback."
        )

    # ---------------------------------
    # DYNAMIC TRADE LEVELS
    # ---------------------------------

    levels = calculate_trade_levels(
        direction=direction,
        spot_price=spot_price,
        atr=atr,
        option_premium=option_premium,
        support=support,
        resistance=resistance,
        atr_stop_multiplier=(
            atr_stop_multiplier
        ),
        minimum_risk_reward=(
            minimum_risk_reward
        ),
        option_stop_percent=(
            option_stop_percent
        ),
    )

    # ---------------------------------
    # LOT-BASED RISK SIZING
    # ---------------------------------

    risk = calculate_trade_risk(
        capital=capital,
        entry_price=levels[
            "option_entry_price"
        ],
        stop_loss_price=levels[
            "option_stop_loss"
        ],
        target_price=levels[
            "option_target"
        ],
        lot_size=resolved_lot_size,
        risk_percent=risk_percent,
        minimum_risk_reward=(
            minimum_risk_reward
        ),
        maximum_capital_usage_percent=(
            maximum_capital_usage_percent
        ),
    )

    # ---------------------------------
    # FINAL AUTHORIZATION
    # ---------------------------------

    allowed = bool(
        risk.get(
            "allowed",
            False,
        )
    )

    decision = (
        "TRADE_ALLOWED"
        if allowed
        else "TRADE_REJECTED"
    )

    reasons = []

    reasons.extend(
        levels.get(
            "reasons",
            [],
        )
    )

    reasons.extend(
        risk.get(
            "reasons",
            [],
        )
    )

    if (
        lot_size_source
        == "CONTRACT"
    ):
        reasons.append(
            "Lot size was obtained from "
            "the selected exchange contract."
        )

    else:
        reasons.append(
            "Contract lot size was unavailable; "
            "manual fallback lot size was used."
        )

    # ---------------------------------
    # FINAL TRADE PLAN
    # ---------------------------------

    return {
        "allowed": allowed,
        "decision": decision,
        "direction": direction,
        "contract": contract,
        "levels": levels,
        "risk": risk,
        "symbol": contract.get(
            "symbol"
        ),
        "option_type": contract.get(
            "option_type"
        ),
        "strike": contract.get(
            "strike"
        ),
        "expiry": contract.get(
            "expiry"
        ),
        "entry_price": levels[
            "option_entry_price"
        ],
        "stop_loss_price": levels[
            "option_stop_loss"
        ],
        "target_price": levels[
            "option_target"
        ],
        "lot_size": (
            resolved_lot_size
        ),
        "lot_size_source": (
            lot_size_source
        ),
        "lots": risk[
            "lots"
        ],
        "quantity": risk[
            "quantity"
        ],
        "required_capital": risk[
            "required_capital"
        ],
        "estimated_maximum_loss": risk[
            "estimated_maximum_loss"
        ],
        "risk_reward_ratio": risk[
            "risk_reward_ratio"
        ],
        "reasons": reasons,
    }
"""
Integrated trade-plan engine.

Combines:
- Selected option contract
- Market ATR and structure
- Dynamic stop-loss and target
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


def build_trade_plan(
    contract,
    direction,
    spot_price,
    atr,
    capital,
    lot_size,
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

    if lot_size <= 0:
        raise ValueError(
            "lot_size must be greater than zero."
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
        lot_size=lot_size,
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
        "lot_size": int(
            lot_size
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
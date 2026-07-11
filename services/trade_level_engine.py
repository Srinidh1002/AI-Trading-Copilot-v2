"""
Dynamic trade-level engine.

Calculates:
- Underlying invalidation level
- Underlying target level
- Option premium stop-loss
- Option premium target

Underlying levels use ATR and market structure.
Option premium levels use controlled percentage risk until
local Greeks are available.

This module does not place orders.
"""


def calculate_trade_levels(
    direction,
    spot_price,
    atr,
    option_premium,
    support=None,
    resistance=None,
    atr_stop_multiplier=1.0,
    minimum_risk_reward=2.0,
    option_stop_percent=20.0,
):
    """
    Calculate dynamic underlying and option trade levels.
    """

    # ---------------------------------
    # VALIDATION
    # ---------------------------------

    if spot_price <= 0:
        raise ValueError(
            "spot_price must be greater than zero."
        )

    if atr <= 0:
        raise ValueError(
            "atr must be greater than zero."
        )

    if option_premium <= 0:
        raise ValueError(
            "option_premium must be greater than zero."
        )

    if atr_stop_multiplier <= 0:
        raise ValueError(
            "atr_stop_multiplier must be greater than zero."
        )

    if minimum_risk_reward <= 0:
        raise ValueError(
            "minimum_risk_reward must be greater than zero."
        )

    if not (
        0 < option_stop_percent < 100
    ):
        raise ValueError(
            "option_stop_percent must be between 0 and 100."
        )

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

    atr_distance = (
        atr
        * atr_stop_multiplier
    )

    reasons = []

    # ---------------------------------
    # UNDERLYING LEVELS
    # ---------------------------------

    if direction == "BULLISH":

        atr_stop = (
            spot_price
            - atr_distance
        )

        underlying_stop = atr_stop

        if (
            support is not None
            and 0 < support < spot_price
        ):
            underlying_stop = min(
                atr_stop,
                float(support),
            )

            reasons.append(
                "Bullish invalidation considers "
                "ATR and market support."
            )

        else:
            reasons.append(
                "Bullish invalidation is based on ATR."
            )

        underlying_risk = (
            spot_price
            - underlying_stop
        )

        underlying_target = (
            spot_price
            + (
                underlying_risk
                * minimum_risk_reward
            )
        )

        if (
            resistance is not None
            and resistance > spot_price
        ):
            resistance = float(
                resistance
            )

            if (
                resistance
                >= underlying_target
            ):
                reasons.append(
                    "Resistance is beyond the minimum "
                    "risk/reward target."
                )

            else:
                reasons.append(
                    "Nearby resistance exists before "
                    "the minimum risk/reward target."
                )

    else:

        atr_stop = (
            spot_price
            + atr_distance
        )

        underlying_stop = atr_stop

        if (
            resistance is not None
            and resistance > spot_price
        ):
            underlying_stop = max(
                atr_stop,
                float(resistance),
            )

            reasons.append(
                "Bearish invalidation considers "
                "ATR and market resistance."
            )

        else:
            reasons.append(
                "Bearish invalidation is based on ATR."
            )

        underlying_risk = (
            underlying_stop
            - spot_price
        )

        underlying_target = (
            spot_price
            - (
                underlying_risk
                * minimum_risk_reward
            )
        )

        if (
            support is not None
            and 0 < support < spot_price
        ):
            support = float(
                support
            )

            if (
                support
                <= underlying_target
            ):
                reasons.append(
                    "Support is beyond the minimum "
                    "risk/reward target."
                )

            else:
                reasons.append(
                    "Nearby support exists before "
                    "the minimum risk/reward target."
                )

    # ---------------------------------
    # OPTION PREMIUM LEVELS
    # ---------------------------------

    option_risk_per_unit = (
        option_premium
        * option_stop_percent
        / 100
    )

    option_stop_loss = (
        option_premium
        - option_risk_per_unit
    )

    option_target = (
        option_premium
        + (
            option_risk_per_unit
            * minimum_risk_reward
        )
    )

    reasons.append(
        "Option premium levels use controlled "
        "percentage risk until local Greeks "
        "are available."
    )

    return {
        "direction": direction,
        "spot_price": round(
            spot_price,
            2,
        ),
        "atr": round(
            atr,
            2,
        ),
        "underlying_stop_loss": round(
            underlying_stop,
            2,
        ),
        "underlying_target": round(
            underlying_target,
            2,
        ),
        "underlying_risk_points": round(
            underlying_risk,
            2,
        ),
        "option_entry_price": round(
            option_premium,
            2,
        ),
        "option_stop_loss": round(
            option_stop_loss,
            2,
        ),
        "option_target": round(
            option_target,
            2,
        ),
        "option_risk_per_unit": round(
            option_risk_per_unit,
            2,
        ),
        "risk_reward_ratio": round(
            minimum_risk_reward,
            2,
        ),
        "reasons": reasons,
    }
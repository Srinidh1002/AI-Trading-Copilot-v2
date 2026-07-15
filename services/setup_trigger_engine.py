"""
Setup and trigger engine.

Classifies a market condition as:
- NO_SETUP
- WAITING_FOR_BREAKOUT
- WAITING_FOR_BREAKDOWN
- TRIGGERED

This module does not place orders.
"""


def evaluate_setup_trigger(
    strategy,
    chart,
    candlestick,
    current_price,
    breakout_buffer_percent=0.0,
):
    """
    Evaluate whether a valid directional setup is waiting
    for confirmation or has already triggered.
    """

    if current_price <= 0:
        raise ValueError(
            "current_price must be greater than zero."
        )

    if breakout_buffer_percent < 0:
        raise ValueError(
            "breakout_buffer_percent cannot be negative."
        )

    strategy = strategy or {}
    chart = chart or {}
    candlestick = candlestick or {}

    direction = str(
        strategy.get(
            "direction",
            "NEUTRAL",
        )
    ).upper()

    market_decision = str(
        strategy.get(
            "decision",
            "NO_TRADE",
        )
    ).upper()

    selected_strategy = str(
        strategy.get(
            "strategy",
            "NO_TRADE",
        )
    ).upper()

    confidence = float(
        strategy.get(
            "direction_confidence",
            strategy.get(
                "confidence",
                0,
            ),
        )
        or 0
    )

    risk_flags = list(
        strategy.get(
            "risk_flags",
            [],
        )
        or []
    )

    chart_patterns = {
        str(pattern).upper()
        for pattern in chart.get(
            "patterns",
            [],
        )
    }

    support = candlestick.get(
        "support"
    )

    resistance = candlestick.get(
        "resistance"
    )

    support = (
        float(support)
        if support is not None
        else None
    )

    resistance = (
        float(resistance)
        if resistance is not None
        else None
    )

    base_result = {
        "status": "NO_SETUP",
        "triggered": False,
        "direction": direction,
        "trigger_type": None,
        "trigger_price": None,
        "current_price": float(
            current_price
        ),
        "support": support,
        "resistance": resistance,
        "confidence": confidence,
        "reasons": [],
    }

    # ---------------------------------
    # INVALID DIRECTION
    # ---------------------------------

    if direction not in {
        "BULLISH",
        "BEARISH",
    }:
        base_result["reasons"].append(
            "No valid directional bias."
        )

        return base_result

    # ---------------------------------
    # BLOCKING RISK
    # ---------------------------------

    if risk_flags:
        base_result["reasons"].append(
            "Setup contains unresolved risk flags."
        )

        return base_result

    # ---------------------------------
    # ALREADY AUTHORIZED
    # ---------------------------------

    if market_decision == "TRADE":

        base_result.update({
            "status": "TRIGGERED",
            "triggered": True,
            "trigger_type": (
                "BREAKOUT"
                if direction == "BULLISH"
                else "BREAKDOWN"
            ),
            "reasons": [
                "Strategy engine has already authorized the trade."
            ],
        })

        return base_result

    # ---------------------------------
    # BULLISH SETUP
    # ---------------------------------

    if direction == "BULLISH":

        if resistance is None:
            base_result["reasons"].append(
                "Resistance level is unavailable."
            )

            return base_result

        trigger_price = (
            resistance
            * (
                1
                + breakout_buffer_percent
                / 100
            )
        )

        base_result[
            "trigger_type"
        ] = "BREAKOUT"

        base_result[
            "trigger_price"
        ] = round(
            trigger_price,
            2,
        )

        if (
            current_price
            > trigger_price
        ):
            base_result.update({
                "status": "TRIGGERED",
                "triggered": True,
                "reasons": [
                    "Price has moved above the breakout trigger."
                ],
            })

            return base_result

        bullish_setup_evidence = bool(
            chart_patterns
            & {
                "DOUBLE_BOTTOM",
                "UPTREND_STRUCTURE",
                "CONSOLIDATION",
                "PRICE_COMPRESSION",
            }
        )

        if bullish_setup_evidence:
            base_result.update({
                "status": "WAITING_FOR_BREAKOUT",
                "reasons": [
                    "Bullish directional setup is waiting "
                    "for price to break resistance."
                ],
            })

            return base_result

    # ---------------------------------
    # BEARISH SETUP
    # ---------------------------------

    if direction == "BEARISH":

        if support is None:
            base_result["reasons"].append(
                "Support level is unavailable."
            )

            return base_result

        trigger_price = (
            support
            * (
                1
                - breakout_buffer_percent
                / 100
            )
        )

        base_result[
            "trigger_type"
        ] = "BREAKDOWN"

        base_result[
            "trigger_price"
        ] = round(
            trigger_price,
            2,
        )

        if (
            current_price
            < trigger_price
        ):
            base_result.update({
                "status": "TRIGGERED",
                "triggered": True,
                "reasons": [
                    "Price has moved below the breakdown trigger."
                ],
            })

            return base_result

        bearish_setup_evidence = bool(
            chart_patterns
            & {
                "DOUBLE_TOP",
                "DOWNTREND_STRUCTURE",
                "CONSOLIDATION",
                "PRICE_COMPRESSION",
            }
        )

        if bearish_setup_evidence:
            base_result.update({
                "status": "WAITING_FOR_BREAKDOWN",
                "reasons": [
                    "Bearish directional setup is waiting "
                    "for price to break support."
                ],
            })

            return base_result

    # ---------------------------------
    # NO ACTIONABLE SETUP
    # ---------------------------------

    base_result["reasons"].append(
        "No actionable setup or trigger was detected."
    )

    return base_result
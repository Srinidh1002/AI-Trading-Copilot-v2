"""
Setup and trigger engine.

Classifies the actionable trigger state while also exposing
research-only setup formation intelligence.

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

    Setup formation fields are research-only and do not
    authorize trades.
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

    confidence = strategy.get(
        "direction_confidence",
        strategy.get(
            "confidence",
            0,
        ),
    )

    evidence_strength_score = strategy.get(
        "evidence_strength_score"
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
        for pattern in (
            chart.get(
                "patterns",
                [],
            )
            or []
        )
    }

    candlestick_patterns = {
        str(pattern).upper()
        for pattern in (
            candlestick.get(
                "patterns",
                [],
            )
            or []
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
        "formation_status": "NO_SETUP",
        "setup_maturity_score": 0,
        "distance_to_trigger": None,
        "distance_to_trigger_percent": None,
        "reasons": [],
    }

    def apply_formation_intelligence(
        trigger_price,
        setup_evidence,
    ):
        distance = abs(
            float(trigger_price)
            - float(current_price)
        )

        distance_percent = (
            distance
            / float(trigger_price)
            * 100
        )

        maturity_score = 0

        if direction in {
            "BULLISH",
            "BEARISH",
        }:
            maturity_score += 20

        if setup_evidence:
            maturity_score += 30

        try:
            numeric_confidence = float(
                confidence
            )
        except (
            TypeError,
            ValueError,
        ):
            numeric_confidence = 0

        if numeric_confidence >= 70:
            maturity_score += 15
        elif numeric_confidence >= 40:
            maturity_score += 10

        try:
            numeric_evidence = float(
                evidence_strength_score
            )
        except (
            TypeError,
            ValueError,
        ):
            numeric_evidence = None

        if numeric_evidence is not None:
            if numeric_evidence >= 70:
                maturity_score += 15
            elif numeric_evidence >= 35:
                maturity_score += 10
            elif numeric_evidence > 0:
                maturity_score += 5

        if distance_percent <= 0.10:
            maturity_score += 20
        elif distance_percent <= 0.25:
            maturity_score += 15
        elif distance_percent <= 0.50:
            maturity_score += 10
        elif distance_percent <= 1.00:
            maturity_score += 5

        maturity_score = min(
            maturity_score,
            100,
        )

        if maturity_score >= 80:
            formation_status = "NEAR_TRIGGER"
        elif maturity_score >= 55:
            formation_status = "DEVELOPING"
        elif maturity_score > 0:
            formation_status = "EARLY_FORMATION"
        else:
            formation_status = "NO_SETUP"

        base_result.update({
            "formation_status": (
                formation_status
            ),
            "setup_maturity_score": (
                maturity_score
            ),
            "distance_to_trigger": round(
                distance,
                2,
            ),
            "distance_to_trigger_percent": round(
                distance_percent,
                4,
            ),
        })

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
        base_result.update({
            "formation_status": "BLOCKED",
        })

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
            "formation_status": "TRIGGERED",
            "setup_maturity_score": 100,
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

        bullish_setup_evidence = bool(
            chart_patterns
            & {
                "DOUBLE_BOTTOM",
                "UPTREND_STRUCTURE",
                "CONSOLIDATION",
                "PRICE_COMPRESSION",
            }
        )

        apply_formation_intelligence(
            trigger_price,
            bullish_setup_evidence,
        )

        if (
            current_price
            > trigger_price
        ):
            base_result.update({
                "status": "TRIGGERED",
                "triggered": True,
                "formation_status": "TRIGGERED",
                "setup_maturity_score": 100,
                "reasons": [
                    "Price has moved above the breakout trigger."
                ],
            })

            return base_result

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

        bearish_setup_evidence = bool(
            chart_patterns
            & {
                "DOUBLE_TOP",
                "DOWNTREND_STRUCTURE",
                "CONSOLIDATION",
                "PRICE_COMPRESSION",
            }
        )

        apply_formation_intelligence(
            trigger_price,
            bearish_setup_evidence,
        )

        if (
            current_price
            < trigger_price
        ):
            base_result.update({
                "status": "TRIGGERED",
                "triggered": True,
                "formation_status": "TRIGGERED",
                "setup_maturity_score": 100,
                "reasons": [
                    "Price has moved below the breakdown trigger."
                ],
            })

            return base_result

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

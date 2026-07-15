"""
Trade Candidate Research Engine.

Measures how close a rejected or developing market setup
is to becoming a valid trade candidate.

Research only.
This module does not authorize trades or place orders.
"""


def evaluate_trade_candidate(
    strategy,
    setup_trigger,
    timeframe=None,
):
    """
    Return research-only trade candidate intelligence.
    """

    strategy = strategy or {}
    setup_trigger = setup_trigger or {}
    timeframe = timeframe or {}

    direction = str(
        strategy.get(
            "direction",
            "NEUTRAL",
        )
    ).upper()

    decision = str(
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

    evidence_strength = strategy.get(
        "evidence_strength_score",
        0,
    )

    risk_flags = list(
        strategy.get(
            "risk_flags",
            [],
        )
        or []
    )

    formation_status = str(
        setup_trigger.get(
            "formation_status",
            "NO_SETUP",
        )
    ).upper()

    setup_maturity = setup_trigger.get(
        "setup_maturity_score",
        0,
    )

    timeframe_alignment = str(
        timeframe.get(
            "alignment",
            "CONFLICTED",
        )
    ).upper()

    try:
        confidence = float(
            confidence
        )
    except (
        TypeError,
        ValueError,
    ):
        confidence = 0.0

    try:
        evidence_strength = float(
            evidence_strength
        )
    except (
        TypeError,
        ValueError,
    ):
        evidence_strength = 0.0

    try:
        setup_maturity = float(
            setup_maturity
        )
    except (
        TypeError,
        ValueError,
    ):
        setup_maturity = 0.0

    passed_conditions = []
    missing_conditions = []

    score = 0

    if direction in {
        "BULLISH",
        "BEARISH",
    }:
        score += 15
        passed_conditions.append(
            "Directional bias established"
        )
    else:
        missing_conditions.append(
            "Directional bias"
        )

    if confidence >= 65:
        score += 20
        passed_conditions.append(
            "Direction confidence"
        )
    else:
        missing_conditions.append(
            "Direction confidence >= 65"
        )

    if evidence_strength >= 65:
        score += 20
        passed_conditions.append(
            "Evidence strength"
        )
    else:
        missing_conditions.append(
            "Evidence strength >= 65"
        )

    if setup_maturity >= 80:
        score += 20
        passed_conditions.append(
            "Setup maturity"
        )
    elif setup_maturity >= 55:
        score += 10
        passed_conditions.append(
            "Developing setup maturity"
        )
        missing_conditions.append(
            "Setup maturity >= 80"
        )
    else:
        missing_conditions.append(
            "Setup maturity >= 55"
        )

    if formation_status in {
        "NEAR_TRIGGER",
        "TRIGGERED",
    }:
        score += 10
        passed_conditions.append(
            "Setup formation"
        )
    else:
        missing_conditions.append(
            "Near-trigger setup formation"
        )

    if timeframe_alignment == "FULL":
        score += 10
        passed_conditions.append(
            "Full timeframe alignment"
        )
    else:
        missing_conditions.append(
            "Full timeframe alignment"
        )

    if not risk_flags:
        score += 5
        passed_conditions.append(
            "No unresolved risk flags"
        )
    else:
        missing_conditions.append(
            "Resolve risk flags"
        )

    score = min(
        int(
            round(
                score
            )
        ),
        100,
    )

    if decision == "TRADE":
        candidate_label = "AUTHORIZED"
    elif score >= 90:
        candidate_label = "VERY_CLOSE"
    elif score >= 75:
        candidate_label = "CLOSE"
    elif score >= 55:
        candidate_label = "DEVELOPING"
    else:
        candidate_label = "WEAK"

    return {
        "research_only": True,
        "trade_authorized": (
            decision == "TRADE"
        ),
        "trade_candidate_score": score,
        "candidate_label": candidate_label,
        "passed_conditions": (
            passed_conditions
        ),
        "missing_conditions": (
            missing_conditions
        ),
    }

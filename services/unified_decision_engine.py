"""
Unified final decision engine.

Combines:
- Strategy decision
- Core risk approval
- Options risk approval

This module is advisory only.
It does not place, modify, or cancel orders.
"""


def make_final_decision(
    strategy,
    core_risk,
    options_risk=None,
):
    reasons = []
    risk_flags = []

    strategy_decision = strategy.get(
        "decision",
        "NO_TRADE",
    ).upper()

    direction = strategy.get(
        "direction",
        "NEUTRAL",
    ).upper()

    selected_strategy = strategy.get(
        "strategy",
        "NO_TRADE",
    ).upper()

    strategy_confidence = int(
        strategy.get(
            "confidence",
            0,
        )
    )

    # -------------------------
    # STRATEGY VALIDATION
    # -------------------------

    if strategy_decision != "TRADE":
        risk_flags.append(
            "Strategy engine rejected the setup."
        )

    if direction not in {
        "BULLISH",
        "BEARISH",
    }:
        risk_flags.append(
            "No valid directional bias."
        )

    reasons.extend(
        strategy.get(
            "confirmations",
            [],
        )
    )

    risk_flags.extend(
        strategy.get(
            "risk_flags",
            [],
        )
    )

    # -------------------------
    # CORE RISK
    # -------------------------

    core_approved = bool(
        core_risk.get(
            "approved",
            False,
        )
    )

    if core_approved:
        reasons.append(
            "Core risk engine approved the trade."
        )
    else:
        risk_flags.append(
            "Core risk engine rejected the trade."
        )

    risk_flags.extend(
        core_risk.get(
            "reasons",
            [],
        )
    )

    # -------------------------
    # OPTIONS RISK
    # -------------------------

    options_approved = True

    if options_risk is not None:

        options_approved = bool(
            options_risk.get(
                "approved",
                False,
            )
        )

        if options_approved:
            reasons.append(
                "Options risk engine approved the contract."
            )
        else:
            risk_flags.append(
                "Options risk engine rejected the contract."
            )

        risk_flags.extend(
            options_risk.get(
                "reasons",
                [],
            )
        )

        risk_flags.extend(
            options_risk.get(
                "warnings",
                [],
            )
        )

    # -------------------------
    # FINAL APPROVAL
    # -------------------------

    approved = (
        strategy_decision == "TRADE"
        and direction
        in {
            "BULLISH",
            "BEARISH",
        }
        and core_approved
        and options_approved
    )

    # -------------------------
    # ACTION
    # -------------------------

    if not approved:
        decision = "NO_TRADE"
        action = "WAIT"

    elif direction == "BULLISH":
        decision = "TRADE"
        action = "BUY_CALL"

    else:
        decision = "TRADE"
        action = "BUY_PUT"

    # -------------------------
    # CONFIDENCE
    # -------------------------

    confidence = strategy_confidence

    if not core_approved:
        confidence = min(
            confidence,
            40,
        )

    if not options_approved:
        confidence = min(
            confidence,
            40,
        )

    if not approved:
        confidence = min(
            confidence,
            50,
        )

    confidence = max(
        0,
        min(
            100,
            confidence,
        ),
    )

    return {
        "decision": decision,
        "action": action,
        "direction": direction,
        "strategy": selected_strategy,
        "confidence": confidence,
        "approved": approved,
        "reasons": reasons,
        "risk_flags": risk_flags,
    }
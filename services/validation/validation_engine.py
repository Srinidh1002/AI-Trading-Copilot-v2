"""
Validation Engine

Performs production validation of the
complete decision pipeline.

This engine NEVER makes trading decisions.
It only validates that every engine
returned a valid response.
"""


def _validate_missing_data(
    *,
    snapshot,
    decision,
    confidence,
    risk,
    trade_score,
    trade_filters,
    master_decision,
    audit,
):
    """
    Validate that every required engine
    returned a response.
    """

    errors = []

    required = {
        "snapshot": snapshot,
        "decision": decision,
        "confidence": confidence,
        "risk": risk,
        "trade_score": trade_score,
        "trade_filters": trade_filters,
        "master_decision": master_decision,
        "audit": audit,
    }

    for name, value in required.items():
        if value is None:
            errors.append(f"{name} is missing")

    return errors


def _validate_contracts(
    *,
    decision,
    confidence,
    risk,
    trade_score,
    trade_filters,
    master_decision,
    audit,
):
    """
    Validate response contracts for every engine.
    """

    errors = []

    contracts = {
        "decision": (
            decision,
            [
                "approved",
            ],
        ),
        "confidence": (
            confidence,
            [
                "confidence",
            ],
        ),
        "risk": (
            risk,
            [
                "approved",
            ],
        ),
        "trade_score": (
            trade_score,
            [
                "approved",
            ],
        ),
        "trade_filters": (
            trade_filters,
            [
                "approved",
                "filters",
                "reasons",
            ],
        ),
        "master_decision": (
            master_decision,
            [
                "approved",
            ],
        ),
        "audit": (
            audit,
            [
                "summary",
                "votes",
                "timeline",
            ],
        ),
    }

    for engine, (data, keys) in contracts.items():

        if not isinstance(data, dict):
            errors.append(
                f"{engine} must return a dictionary"
            )
            continue

        for key in keys:
            if key not in data:
                errors.append(
                    f"{engine} missing '{key}'"
                )

    return errors


def _validate_pipeline_consistency(
    *,
    decision,
    risk,
    trade_score,
    trade_filters,
    master_decision,
):
    """
    Validate logical consistency between engines.
    """

    warnings = []

    if (
        decision.get("approved", False)
        and not risk.get("approved", False)
    ):
        warnings.append(
            "Decision approved while Risk Engine rejected."
        )

    if (
        decision.get("approved", False)
        and not trade_score.get("approved", False)
    ):
        warnings.append(
            "Decision approved while Trade Score Engine rejected."
        )

    if (
        decision.get("approved", False)
        and not trade_filters.get("approved", False)
    ):
        warnings.append(
            "Decision approved while Trade Filter Engine rejected."
        )

    if (
        master_decision.get("approved", False)
        and not decision.get("approved", False)
    ):
        warnings.append(
            "Master Decision approved while Decision Engine rejected."
        )

    return warnings


def _validate_decision_consistency(
    *,
    confidence,
    master_decision,
):
    """
    Validate the consistency of the final decision.
    """

    warnings = []

    confidence_value = confidence.get(
        "confidence",
        0,
    )

    if (
        master_decision.get("approved", False)
        and confidence_value < 70
    ):
        warnings.append(
            "Master Decision approved with low confidence."
        )

    if (
        not master_decision.get("approved", False)
        and confidence_value >= 90
    ):
        warnings.append(
            "High confidence but trade rejected."
        )

    return warnings


def _build_validation_report(
    errors,
    warnings,
):
    """
    Build the final production validation report.
    """

    return {
        "status": (
            "PASS"
            if len(errors) == 0
            else "FAIL"
        ),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "ready_for_production": len(errors) == 0,
    }


def validate_pipeline(
    *,
    snapshot,
    decision,
    confidence,
    risk,
    trade_score,
    trade_filters,
    master_decision,
    audit,
):
    """
    Validate the complete decision pipeline.
    """

    errors = []
    warnings = []

    errors.extend(
        _validate_missing_data(
            snapshot=snapshot,
            decision=decision,
            confidence=confidence,
            risk=risk,
            trade_score=trade_score,
            trade_filters=trade_filters,
            master_decision=master_decision,
            audit=audit,
        )
    )

    errors.extend(
        _validate_contracts(
            decision=decision,
            confidence=confidence,
            risk=risk,
            trade_score=trade_score,
            trade_filters=trade_filters,
            master_decision=master_decision,
            audit=audit,
        )
    )

    warnings.extend(
        _validate_pipeline_consistency(
            decision=decision,
            risk=risk,
            trade_score=trade_score,
            trade_filters=trade_filters,
            master_decision=master_decision,
        )
    )

    warnings.extend(
        _validate_decision_consistency(
            confidence=confidence,
            master_decision=master_decision,
        )
    )

    report = _build_validation_report(
        errors,
        warnings,
    )

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "report": report,
    }
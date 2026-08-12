"""Task 9 live-session executed PAPER trade counting authority."""
from __future__ import annotations

from services.contracts.task9_live_paper_trade_counting_decision_v1 import (
    Task9LivePaperTradeCountingDecisionV1,
)
from services.contracts.task9_live_paper_trade_counting_input_v1 import (
    Task9LivePaperTradeCountingInputV1,
)


_NO_TRADE_OUTCOMES = {
    "NO_TRADE_CORRECT",
    "NO_TRADE_MISSED_MOVE",
}


def _decision(
    value: Task9LivePaperTradeCountingInputV1,
    *,
    status: str,
    reasons: tuple[str, ...],
    trade_target_countable: bool = False,
    no_trade_record: bool = False,
    wait_record: bool = False,
    pending: bool = False,
) -> Task9LivePaperTradeCountingDecisionV1:
    reconciliation = value.reconciliation

    return Task9LivePaperTradeCountingDecisionV1(
        decision_id=(
            "task9-trade-count:"
            f"{value.official_run_id}:"
            f"{value.prediction.prediction_id}"
        ),
        prediction_id=value.prediction.prediction_id,
        market=value.prediction.underlying_symbol,
        status=status,
        trade_target_countable=trade_target_countable,
        no_trade_record=no_trade_record,
        wait_record=wait_record,
        pending=pending,
        position_id=(
            reconciliation.position_id
            if reconciliation is not None
            else None
        ),
        reason_codes=reasons,
        evaluated_at=value.evaluated_at,
    )


def evaluate_task9_live_paper_trade_counting(
    value: Task9LivePaperTradeCountingInputV1,
) -> Task9LivePaperTradeCountingDecisionV1:
    """Classify one live record for the Task 9 100-trade target."""

    if type(value) is not Task9LivePaperTradeCountingInputV1:
        raise TypeError("value")

    prediction = value.prediction
    outcome = value.lifecycle_outcome
    reconciliation = value.reconciliation

    if value.record_source == "REPLAY":
        return _decision(
            value,
            status="EXCLUDED_REPLAY",
            reasons=("REPLAY_NEVER_COUNTS_TOWARD_LIVE_TARGET",),
        )

    if value.record_source != "LIVE_REAL_TIME":
        return _decision(
            value,
            status="EXCLUDED_NON_LIVE_SOURCE",
            reasons=(f"RECORD_SOURCE_{value.record_source}",),
        )

    if value.record_run_id != value.official_run_id:
        return _decision(
            value,
            status="EXCLUDED_RUN_MISMATCH",
            reasons=("OFFICIAL_RUN_ID_MISMATCH",),
        )

    if prediction.completed_at < value.official_start_at:
        return _decision(
            value,
            status="EXCLUDED_PRE_START",
            reasons=("PREDICTION_PRECEDES_OFFICIAL_START",),
        )

    if value.session_status != "REAL_TIME_MARKET_SESSION":
        return _decision(
            value,
            status="EXCLUDED_OUT_OF_SESSION",
            reasons=(f"SESSION_STATUS_{value.session_status}",),
        )

    if value.evidence_status == "INVALID":
        return _decision(
            value,
            status="EXCLUDED_INVALID_EVIDENCE",
            reasons=("EVIDENCE_INVALID",),
        )

    if value.evidence_status == "DATA_INCIDENT":
        provider_reason_codes = tuple(
            code
            for code in (
                *prediction.errors,
                *prediction.blockers,
                *prediction.rationale,
            )
            if code == "HISTORICAL-DATA_RATE_LIMITED"
        )
        return _decision(
            value,
            status="EXCLUDED_DATA_INCIDENT",
            reasons=("DATA_INCIDENT", *dict.fromkeys(provider_reason_codes)),
        )

    if prediction.terminal_status != "COMPLETED":
        return _decision(
            value,
            status="EXCLUDED_PREDICTION_FAILURE",
            reasons=(f"PREDICTION_STATUS_{prediction.terminal_status}",),
        )

    action = prediction.predicted_action
    if action in {"WAIT", "NO_TRADE"}:
        if outcome is None:
            return _decision(
                value,
                status="PENDING",
                reasons=("LIFECYCLE_EVIDENCE_PENDING",),
                pending=True,
            )
        if outcome.evaluation_status == "UNRESOLVED":
            return _decision(
                value,
                status="PENDING",
                reasons=("LIFECYCLE_OUTCOME_UNRESOLVED",),
                pending=True,
            )
        if outcome.evaluation_status != "RESOLVED":
            return _decision(
                value,
                status="EXCLUDED_UNRESOLVED",
                reasons=(f"LIFECYCLE_STATUS_{outcome.evaluation_status}",),
            )
        if outcome.entry_occurred:
            return _decision(
                value,
                status="EXCLUDED_RECONCILIATION",
                reasons=(f"{action}_MUST_NOT_HAVE_PAPER_ENTRY",),
            )
        if outcome.outcome not in _NO_TRADE_OUTCOMES:
            return _decision(
                value,
                status="EXCLUDED_UNRESOLVED",
                reasons=(f"INVALID_{action}_OUTCOME_{outcome.outcome}",),
            )
        return _decision(
            value,
            status=action,
            reasons=(
                (
                    f"WAIT_{outcome.outcome}_RECORDED_SEPARATELY"
                    if action == "WAIT"
                    else f"{outcome.outcome}_RECORDED_SEPARATELY"
                ),
            ),
            no_trade_record=action == "NO_TRADE",
            wait_record=action == "WAIT",
        )

    if outcome is None or reconciliation is None:
        return _decision(
            value,
            status="PENDING",
            reasons=("LIFECYCLE_EVIDENCE_PENDING",),
            pending=True,
        )

    if outcome.evaluation_status == "UNRESOLVED":
        return _decision(
            value,
            status="PENDING",
            reasons=("LIFECYCLE_OUTCOME_UNRESOLVED",),
            pending=True,
        )

    if outcome.evaluation_status != "RESOLVED":
        return _decision(
            value,
            status="EXCLUDED_UNRESOLVED",
            reasons=(
                f"LIFECYCLE_STATUS_{outcome.evaluation_status}",
            ),
        )

    if reconciliation.status != "RECONCILED":
        return _decision(
            value,
            status="EXCLUDED_RECONCILIATION",
            reasons=(
                f"RECONCILIATION_STATUS_{reconciliation.status}",
                *reconciliation.blockers,
            ),
        )

    if not reconciliation.counting_eligible:
        return _decision(
            value,
            status="EXCLUDED_RECONCILIATION",
            reasons=("RECONCILIATION_NOT_COUNTING_ELIGIBLE",),
        )

    if not outcome.entry_occurred:
        return _decision(
            value,
            status="EXCLUDED_NO_ENTRY",
            reasons=("PAPER_ENTRY_DID_NOT_OCCUR",),
        )

    if reconciliation.position_id is None:
        return _decision(
            value,
            status="EXCLUDED_RECONCILIATION",
            reasons=("RECONCILED_TRADE_MISSING_POSITION_ID",),
        )

    return _decision(
        value,
        status="COUNTED_TRADE",
        reasons=(),
        trade_target_countable=True,
    )

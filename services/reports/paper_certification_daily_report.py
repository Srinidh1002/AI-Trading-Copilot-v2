"""Authoritative daily PAPER certification reporting."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime

from services.contracts.paper_certification_reporting_v1 import (
    CertificationAuditItemV1,
    CertificationDuplicateAttemptV1,
    CertificationIncidentV1,
    CertificationPredictionFactV1,
    PaperCertificationDailyReportV1,
    PredictionCertificationAnalyticsContextV1,
)
from services.contracts.paper_trade_position_v1 import (
    PaperTradePositionV1,
)
from services.contracts.prediction_certification_counting_decision_v1 import (
    PredictionCertificationCountingDecisionV1,
)
from services.contracts.prediction_lifecycle_outcome_record_v1 import (
    PredictionLifecycleOutcomeRecordV1,
)
from services.contracts.prediction_lifecycle_reconciliation_result_v1 import (
    PredictionLifecycleReconciliationResultV1,
)
from services.contracts.prediction_record_v1 import (
    PredictionRecordV1,
)


_SUCCESS_OUTCOMES = {
    "T1_HIT",
    "T2_HIT",
    "T3_HIT",
    "EARLY_EXIT_PROFIT",
    "NO_TRADE_CORRECT",
}
_FAILURE_OUTCOMES = {
    "STOP_HIT",
    "EARLY_EXIT_LOSS",
    "NO_TRADE_MISSED_MOVE",
}
_OUTCOMES = {
    "T1_HIT",
    "T2_HIT",
    "T3_HIT",
    "STOP_HIT",
    "EARLY_EXIT_PROFIT",
    "EARLY_EXIT_LOSS",
    "EXPIRED_WITHOUT_ENTRY",
    "INVALIDATED_BEFORE_ENTRY",
    "NO_TRADE_CORRECT",
    "NO_TRADE_MISSED_MOVE",
    "DATA_UNAVAILABLE",
    "UNRESOLVED",
    "PENDING",
}


def _typed_tuple(value, expected, name):
    if type(value) is not tuple or any(
        type(item) is not expected
        for item in value
    ):
        raise TypeError(name)
    return value


def _unique(values, key, name):
    result = {}
    for item in values:
        identity = key(item)
        if identity in result:
            raise ValueError(f"duplicate {name}")
        result[identity] = item
    return result


def _distribution(
    values,
    vocabulary=(),
) -> tuple[tuple[str, int], ...]:
    counts = Counter(values)
    keys = set(counts) | set(vocabulary)
    return tuple(
        (key, counts[key])
        for key in sorted(keys)
    )


def _terminal(position: PaperTradePositionV1) -> bool:
    return (
        position.lifecycle_state.startswith("CLOSED_")
        or position.lifecycle_state == "CANCELLED"
    )


def _success(outcome: str) -> bool | None:
    if outcome in _SUCCESS_OUTCOMES:
        return True
    if outcome in _FAILURE_OUTCOMES:
        return False
    return None


def build_paper_certification_daily_report(
    *,
    report_id: str,
    session_date: date,
    generated_at: datetime,
    starting_capital: float,
    predictions: tuple[PredictionRecordV1, ...],
    counting_decisions: tuple[
        PredictionCertificationCountingDecisionV1, ...
    ],
    lifecycle_outcomes: tuple[
        PredictionLifecycleOutcomeRecordV1, ...
    ],
    reconciliations: tuple[
        PredictionLifecycleReconciliationResultV1, ...
    ],
    positions: tuple[PaperTradePositionV1, ...],
    analytics_contexts: tuple[
        PredictionCertificationAnalyticsContextV1, ...
    ] = (),
    incidents: tuple[CertificationIncidentV1, ...] = (),
    duplicate_attempts: tuple[
        CertificationDuplicateAttemptV1, ...
    ] = (),
) -> PaperCertificationDailyReportV1:
    """Build one exact report from supplied authoritative records."""

    predictions = _typed_tuple(
        predictions,
        PredictionRecordV1,
        "predictions",
    )
    counting_decisions = _typed_tuple(
        counting_decisions,
        PredictionCertificationCountingDecisionV1,
        "counting_decisions",
    )
    lifecycle_outcomes = _typed_tuple(
        lifecycle_outcomes,
        PredictionLifecycleOutcomeRecordV1,
        "lifecycle_outcomes",
    )
    reconciliations = _typed_tuple(
        reconciliations,
        PredictionLifecycleReconciliationResultV1,
        "reconciliations",
    )
    positions = _typed_tuple(
        positions,
        PaperTradePositionV1,
        "positions",
    )
    analytics_contexts = _typed_tuple(
        analytics_contexts,
        PredictionCertificationAnalyticsContextV1,
        "analytics_contexts",
    )
    incidents = _typed_tuple(
        incidents,
        CertificationIncidentV1,
        "incidents",
    )
    duplicate_attempts = _typed_tuple(
        duplicate_attempts,
        CertificationDuplicateAttemptV1,
        "duplicate_attempts",
    )

    if type(session_date) is not date:
        raise TypeError("session_date")
    if (
        not isinstance(generated_at, datetime)
        or generated_at.tzinfo is None
        or generated_at.utcoffset() is None
    ):
        raise ValueError("generated_at")

    ordered_predictions = tuple(
        sorted(
            predictions,
            key=lambda item: (
                item.completed_at,
                item.prediction_id,
            ),
        )
    )
    prediction_by_id = _unique(
        ordered_predictions,
        lambda item: item.prediction_id,
        "prediction_id",
    )
    decision_by_prediction = _unique(
        counting_decisions,
        lambda item: item.prediction_id,
        "counting decision",
    )
    outcome_by_prediction = _unique(
        lifecycle_outcomes,
        lambda item: item.prediction_id,
        "lifecycle outcome",
    )
    reconciliation_by_prediction = _unique(
        reconciliations,
        lambda item: item.prediction_id,
        "reconciliation",
    )
    position_by_id = _unique(
        positions,
        lambda item: item.position_id,
        "position_id",
    )
    context_by_prediction = _unique(
        analytics_contexts,
        lambda item: item.prediction_id,
        "analytics context",
    )

    prediction_ids = set(prediction_by_id)
    if set(decision_by_prediction) != prediction_ids:
        raise ValueError(
            "every prediction requires exactly one counting decision"
        )
    for source_name, source in (
        ("lifecycle outcome", outcome_by_prediction),
        ("reconciliation", reconciliation_by_prediction),
        ("analytics context", context_by_prediction),
    ):
        unknown = set(source) - prediction_ids
        if unknown:
            raise ValueError(
                f"{source_name} references unknown prediction"
            )

    referenced_position_ids = tuple(
        item.position_id
        for item in reconciliations
        if item.position_id is not None
    )
    if len(set(referenced_position_ids)) != len(
        referenced_position_ids
    ):
        raise ValueError(
            "one PAPER position cannot reconcile multiple predictions"
        )
    if not set(referenced_position_ids).issubset(position_by_id):
        raise ValueError(
            "reconciliation references unknown position"
        )

    for prediction in ordered_predictions:
        if prediction.completed_at.date() != session_date:
            raise ValueError(
                "prediction lies outside daily session"
            )

    for incident in incidents:
        if incident.occurred_at.date() != session_date:
            raise ValueError("incident lies outside daily session")
    for attempt in duplicate_attempts:
        if attempt.occurred_at.date() != session_date:
            raise ValueError(
                "duplicate attempt lies outside daily session"
            )

    facts: list[CertificationPredictionFactV1] = []
    excluded: list[CertificationAuditItemV1] = []
    unresolved: list[CertificationAuditItemV1] = []

    for prediction in ordered_predictions:
        prediction_id = prediction.prediction_id
        decision = decision_by_prediction[prediction_id]
        outcome = outcome_by_prediction.get(prediction_id)
        reconciliation = reconciliation_by_prediction.get(
            prediction_id
        )
        context = context_by_prediction.get(
            prediction_id,
            PredictionCertificationAnalyticsContextV1(
                prediction_id=prediction_id,
            ),
        )

        if (
            decision.underlying_symbol
            != prediction.underlying_symbol
            or decision.exchange != prediction.exchange
            or decision.predicted_action
            != prediction.predicted_action
        ):
            raise ValueError(
                "prediction/counting identity mismatch"
            )
        if outcome is not None and (
            outcome.underlying_symbol
            != prediction.underlying_symbol
            or outcome.exchange != prediction.exchange
            or outcome.predicted_action
            != prediction.predicted_action
        ):
            raise ValueError(
                "prediction/outcome identity mismatch"
            )
        if reconciliation is not None and (
            reconciliation.underlying_symbol
            != prediction.underlying_symbol
            or reconciliation.exchange != prediction.exchange
            or reconciliation.predicted_action
            != prediction.predicted_action
            or reconciliation.lifecycle_outcome_id
            != (
                outcome.outcome_id
                if outcome is not None
                else reconciliation.lifecycle_outcome_id
            )
        ):
            raise ValueError(
                "prediction/reconciliation identity mismatch"
            )

        position = (
            position_by_id.get(reconciliation.position_id)
            if reconciliation is not None
            and reconciliation.position_id is not None
            else None
        )

        lifecycle_status = (
            outcome.evaluation_status
            if outcome is not None
            else "MISSING"
        )
        outcome_name = (
            outcome.outcome
            if outcome is not None
            else "PENDING"
        )
        reconciliation_status = (
            reconciliation.status
            if reconciliation is not None
            else "MISSING"
        )

        officially_counted = bool(
            decision.countable
            and outcome is not None
            and outcome.evaluation_status == "RESOLVED"
            and reconciliation is not None
            and reconciliation.status == "RECONCILED"
            and reconciliation.counting_eligible
        )

        if officially_counted:
            classification = "OFFICIAL"
        elif not decision.countable and not decision.pending:
            classification = "EXCLUDED"
            reasons = list(decision.reason_codes)
            status = decision.status
            if outcome is not None and (
                outcome.evaluation_status
                == "DATA_UNAVAILABLE"
            ):
                status = "EXCLUDED_DATA_UNAVAILABLE"
                reasons.extend(outcome.blockers)
            if reconciliation is not None and (
                reconciliation.status
                in {"DATA_UNAVAILABLE", "BLOCKED"}
            ):
                status = (
                    "EXCLUDED_RECONCILIATION_"
                    f"{reconciliation.status}"
                )
                reasons.extend(reconciliation.blockers)
            excluded.append(
                CertificationAuditItemV1(
                    prediction_id=prediction_id,
                    status=status,
                    reason_codes=tuple(
                        dict.fromkeys(reasons)
                    )
                    or ("NOT_OFFICIALLY_COUNTABLE",),
                )
            )
        elif (
            decision.pending
            or outcome is None
            or outcome.evaluation_status == "UNRESOLVED"
            or reconciliation is None
            or reconciliation.status == "PENDING"
        ):
            classification = "PENDING"
            reasons = []
            if decision.pending:
                reasons.extend(decision.reason_codes)
            if outcome is None:
                reasons.append("LIFECYCLE_OUTCOME_MISSING")
            elif outcome.evaluation_status == "UNRESOLVED":
                reasons.extend(outcome.blockers)
            if reconciliation is None:
                reasons.append("RECONCILIATION_MISSING")
            elif reconciliation.status == "PENDING":
                reasons.extend(reconciliation.blockers)
            unresolved.append(
                CertificationAuditItemV1(
                    prediction_id=prediction_id,
                    status="PENDING",
                    reason_codes=tuple(
                        dict.fromkeys(reasons)
                    )
                    or ("PENDING_EVIDENCE",),
                )
            )
        else:
            classification = "EXCLUDED"
            reasons = list(decision.reason_codes)
            status = decision.status
            if outcome is not None and (
                outcome.evaluation_status
                == "DATA_UNAVAILABLE"
            ):
                status = "EXCLUDED_DATA_UNAVAILABLE"
                reasons.extend(outcome.blockers)
            if reconciliation is not None and (
                reconciliation.status
                in {"DATA_UNAVAILABLE", "BLOCKED"}
            ):
                status = (
                    "EXCLUDED_RECONCILIATION_"
                    f"{reconciliation.status}"
                )
                reasons.extend(reconciliation.blockers)
            excluded.append(
                CertificationAuditItemV1(
                    prediction_id=prediction_id,
                    status=status,
                    reason_codes=tuple(
                        dict.fromkeys(reasons)
                    )
                    or ("NOT_OFFICIALLY_COUNTABLE",),
                )
            )

        closed = (
            position is not None
            and _terminal(position)
        )
        gross_pnl = (
            position.realized_gross_pnl
            if closed
            else 0.0
        )
        net_pnl = (
            position.realized_net_pnl
            if closed
            else 0.0
        )
        facts.append(
            CertificationPredictionFactV1(
                prediction_id=prediction_id,
                parent_cycle_id=prediction.parent_cycle_id,
                market=prediction.underlying_symbol,
                action=prediction.predicted_action,
                direction=prediction.predicted_direction,
                confidence=prediction.confidence,
                confidence_band=context.confidence_band,
                regime=context.regime,
                time_of_day=context.time_of_day,
                contract_quality=context.contract_quality,
                spread_quality=context.spread_quality,
                liquidity_quality=context.liquidity_quality,
                parent_selected=prediction.parent_selected,
                parent_decision=prediction.parent_decision,
                counting_status=decision.status,
                officially_counted=officially_counted,
                lifecycle_status=lifecycle_status,
                outcome=outcome_name,
                reconciliation_status=reconciliation_status,
                entry_occurred=(
                    outcome.entry_occurred
                    if outcome is not None
                    else False
                ),
                closed_position=closed,
                success=(
                    _success(outcome_name)
                    if officially_counted
                    else None
                ),
                gross_pnl=gross_pnl,
                net_pnl=net_pnl,
                policy_version=(
                    outcome.policy_version
                    if outcome is not None
                    else decision.policy_version
                ),
                engine_contributions=(
                    context.engine_contributions
                ),
                pillar_contributions=(
                    context.pillar_contributions
                ),
            )
        )

    terminal_positions = tuple(
        item
        for item in positions
        if _terminal(item)
    )
    for position in terminal_positions:
        if not position.exit_fills:
            raise ValueError(
                "terminal position requires exit fills"
            )
        if position.exit_fills[-1].filled_at.date() != session_date:
            raise ValueError(
                "closed position lies outside daily session"
            )

    gross_pnl = sum(
        item.realized_gross_pnl
        for item in terminal_positions
    )
    net_pnl = sum(
        item.realized_net_pnl
        for item in terminal_positions
    )
    wins = sum(
        item.realized_net_pnl > 0.0
        for item in terminal_positions
    )
    losses = sum(
        item.realized_net_pnl < 0.0
        for item in terminal_positions
    )
    break_even = len(terminal_positions) - wins - losses

    official_count = sum(
        item.officially_counted
        for item in facts
    )
    completed_count = sum(
        item.lifecycle_status == "RESOLVED"
        for item in facts
    )
    selected_markets = [
        item.market
        for item in facts
        if item.parent_selected
    ]

    return PaperCertificationDailyReportV1(
        report_id=report_id,
        session_date=session_date,
        generated_at=generated_at,
        starting_capital=starting_capital,
        ending_capital=starting_capital + net_pnl,
        source_prediction_count=len(facts),
        official_prediction_count=official_count,
        completed_outcome_count=completed_count,
        pending_outcome_count=len(unresolved),
        excluded_prediction_count=len(excluded),
        no_trade_cycle_count=len(
            {
                item.parent_cycle_id
                for item in facts
                if item.parent_decision == "NO_TRADE"
            }
        ),
        entry_count=len(positions),
        closed_position_count=len(terminal_positions),
        win_count=wins,
        loss_count=losses,
        break_even_count=break_even,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        market_distribution=_distribution(
            (item.market for item in facts),
            ("NIFTY", "SENSEX"),
        ),
        action_distribution=_distribution(
            (item.action for item in facts),
            ("CALL", "PUT", "WAIT"),
        ),
        selected_market_distribution=_distribution(
            selected_markets,
            ("NIFTY", "SENSEX"),
        ),
        outcome_distribution=_distribution(
            (item.outcome for item in facts),
            _OUTCOMES,
        ),
        reconciliation_distribution=_distribution(
            (item.reconciliation_status for item in facts),
            (
                "RECONCILED",
                "PENDING",
                "DATA_UNAVAILABLE",
                "BLOCKED",
                "MISSING",
            ),
        ),
        incident_distribution=_distribution(
            (item.incident_type for item in incidents),
            ("DATA_PROVIDER", "LIFECYCLE", "SYSTEM"),
        ),
        duplicate_distribution=_distribution(
            (item.duplicate_type for item in duplicate_attempts),
            (
                "PROVIDER_CALL",
                "PREDICTION",
                "ENTRY",
                "EXIT",
                "OTHER",
            ),
        ),
        prediction_facts=tuple(facts),
        excluded_audit=tuple(excluded),
        unresolved_audit=tuple(unresolved),
        incidents=incidents,
        duplicate_attempts=duplicate_attempts,
    )

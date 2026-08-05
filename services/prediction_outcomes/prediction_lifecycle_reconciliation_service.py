"""Deterministic prediction-to-PAPER-lifecycle reconciliation."""
from __future__ import annotations

import math
from datetime import datetime

from services.contracts.paper_trade_position_v1 import (
    PaperTradePositionV1,
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


_NO_POSITION_OUTCOMES = {
    "EXPIRED_WITHOUT_ENTRY",
    "INVALIDATED_BEFORE_ENTRY",
}
_TARGET_LEVEL = {
    "TARGET_1": 1,
    "TARGET_2": 2,
    "TARGET_3": 3,
}
_TERMINAL_REASON_BY_EVENT = {
    "STOP": {"STOP"},
    "INVALIDATED": {"INVALIDATION"},
    "SESSION_CLOSE": {"SESSION_CLOSE"},
    "EXPIRY": {"EXPIRY_CLOSE"},
    "T3": {"TARGET_3"},
    "EARLY_EXIT": {
        "INVALIDATION",
        "SESSION_CLOSE",
        "EXPIRY_CLOSE",
        "CANCELLED",
        "RUNNER_CLOSE",
    },
}


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _close(left: float, right: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def _result(
    *,
    prediction: PredictionRecordV1,
    outcome: PredictionLifecycleOutcomeRecordV1,
    position: PaperTradePositionV1 | None,
    reconciled_at: datetime,
    status: str,
    identity_matches: bool,
    entry_matches: bool | None,
    terminal_matches: bool | None,
    fill_sequence_matches: bool | None,
    quantity_matches: bool | None,
    pnl_matches: bool | None,
    blockers: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> PredictionLifecycleReconciliationResultV1:
    return PredictionLifecycleReconciliationResultV1(
        reconciliation_id=(
            f"prediction-lifecycle-reconciliation:"
            f"{prediction.prediction_id}:"
            f"{outcome.outcome_id}"
        ),
        prediction_id=prediction.prediction_id,
        lifecycle_outcome_id=outcome.outcome_id,
        position_id=(
            position.position_id
            if position is not None
            else None
        ),
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        predicted_action=prediction.predicted_action,
        lifecycle_outcome=outcome.outcome,
        position_lifecycle_state=(
            position.lifecycle_state
            if position is not None
            else None
        ),
        reconciled_at=reconciled_at,
        status=status,
        reconciliation_complete=(status == "RECONCILED"),
        counting_eligible=(status == "RECONCILED"),
        identity_matches=identity_matches,
        entry_matches=entry_matches,
        terminal_matches=terminal_matches,
        fill_sequence_matches=fill_sequence_matches,
        quantity_matches=quantity_matches,
        pnl_matches=pnl_matches,
        blockers=blockers,
        warnings=warnings,
    )


def _prediction_outcome_identity(
    prediction: PredictionRecordV1,
    outcome: PredictionLifecycleOutcomeRecordV1,
) -> bool:
    return (
        outcome.prediction_id == prediction.prediction_id
        and outcome.parent_cycle_id
        == prediction.parent_cycle_id
        and outcome.decision_result_id
        == prediction.decision_result_id
        and outcome.underlying_symbol
        == prediction.underlying_symbol
        and outcome.exchange == prediction.exchange
        and outcome.predicted_action
        == prediction.predicted_action
    )


def _position_identity(
    prediction: PredictionRecordV1,
    position: PaperTradePositionV1,
) -> bool:
    action_matches = (
        position.option_type.upper()
        == prediction.predicted_action
    )
    market_matches = (
        position.underlying_symbol.upper()
        == prediction.underlying_symbol
        and position.market.upper()
        == prediction.underlying_symbol
    )
    return action_matches and market_matches


def _fill_checks(
    position: PaperTradePositionV1,
) -> tuple[
    bool,
    bool,
    bool,
    tuple,
]:
    fills = tuple(
        sorted(
            position.exit_fills,
            key=lambda item: (
                item.filled_at,
                item.fill_id,
            ),
        )
    )
    identifiers = tuple(
        item.fill_id
        for item in fills
    )
    sequence_matches = (
        len(set(identifiers)) == len(identifiers)
        and all(
            item.filled_at >= position.opened_at
            for item in fills
        )
        and all(
            fills[index].filled_at
            <= fills[index + 1].filled_at
            for index in range(len(fills) - 1)
        )
    )

    exited_quantity = sum(
        item.filled_quantity
        for item in fills
    )
    quantity_matches = (
        exited_quantity
        == position.initial_quantity
        - position.remaining_quantity
        and position.remaining_quantity
        == position.remaining_lot_count
        * position.lot_size
    )

    terminal = (
        position.lifecycle_state.startswith("CLOSED_")
        or position.lifecycle_state == "CANCELLED"
    )
    gross = sum(
        (
            item.fill_price
            - position.entry_price
        )
        * item.filled_quantity
        for item in fills
    )
    costs = (
        position.entry_fill.estimated_trading_cost
        + sum(
            item.estimated_trading_cost
            for item in fills
        )
    )
    expected_net = gross - costs

    pnl_matches = (
        (
            not terminal
            and _close(
                position.total_pnl,
                position.realized_net_pnl
                + position.unrealized_pnl,
            )
        )
        or (
            terminal
            and position.remaining_quantity == 0
            and _close(position.unrealized_pnl, 0.0)
            and _close(
                position.realized_gross_pnl,
                gross,
            )
            and _close(
                position.realized_net_pnl,
                expected_net,
            )
            and _close(
                position.total_pnl,
                expected_net,
            )
        )
    )

    return (
        sequence_matches,
        quantity_matches,
        pnl_matches,
        fills,
    )


def _terminal_matches(
    *,
    outcome: PredictionLifecycleOutcomeRecordV1,
    position: PaperTradePositionV1,
    fills: tuple,
) -> bool:
    terminal = (
        position.lifecycle_state.startswith("CLOSED_")
        or position.lifecycle_state == "CANCELLED"
    )
    if not terminal or not fills:
        return False

    last_fill = fills[-1]
    target_level = max(
        (
            _TARGET_LEVEL.get(
                item.fill_reason,
                0,
            )
            for item in fills
        ),
        default=0,
    )

    expected_target = {
        "T1_HIT": 1,
        "T2_HIT": 2,
        "T3_HIT": 3,
    }.get(outcome.outcome)

    if expected_target is not None:
        outcome_matches = (
            target_level == expected_target
        )
    elif outcome.outcome == "STOP_HIT":
        outcome_matches = (
            target_level == 0
            and last_fill.fill_reason == "STOP"
        )
    elif outcome.outcome in {
        "EARLY_EXIT_PROFIT",
        "EARLY_EXIT_LOSS",
    }:
        expected_profit = (
            outcome.outcome == "EARLY_EXIT_PROFIT"
        )
        outcome_matches = (
            target_level == 0
            and last_fill.fill_reason
            not in {
                "STOP",
                "TARGET_1",
                "TARGET_2",
                "TARGET_3",
            }
            and (
                position.realized_net_pnl > 0.0
            )
            == expected_profit
        )
    else:
        return False

    event_reasons = _TERMINAL_REASON_BY_EVENT.get(
        outcome.terminal_event_type
    )
    reason_matches = (
        event_reasons is None
        or last_fill.fill_reason in event_reasons
    )
    timestamp_matches = (
        outcome.terminal_event_at
        == last_fill.filled_at
    )
    premium_matches = (
        outcome.terminal_option_premium is None
        or _close(
            outcome.terminal_option_premium,
            last_fill.fill_price,
        )
    )

    return (
        outcome_matches
        and reason_matches
        and timestamp_matches
        and premium_matches
    )


def reconcile_prediction_lifecycle(
    *,
    prediction: PredictionRecordV1,
    outcome: PredictionLifecycleOutcomeRecordV1,
    position: PaperTradePositionV1 | None,
    reconciled_at: datetime,
) -> PredictionLifecycleReconciliationResultV1:
    """Reconcile prediction outcome with immutable PAPER position truth."""

    if type(prediction) is not PredictionRecordV1:
        raise TypeError("prediction")
    if (
        type(outcome)
        is not PredictionLifecycleOutcomeRecordV1
    ):
        raise TypeError("outcome")
    if (
        position is not None
        and type(position) is not PaperTradePositionV1
    ):
        raise TypeError("position")

    at = _aware(reconciled_at, "reconciled_at")
    identity_matches = _prediction_outcome_identity(
        prediction,
        outcome,
    )
    if not identity_matches:
        return _result(
            prediction=prediction,
            outcome=outcome,
            position=position,
            reconciled_at=at,
            status="BLOCKED",
            identity_matches=False,
            entry_matches=None,
            terminal_matches=None,
            fill_sequence_matches=None,
            quantity_matches=None,
            pnl_matches=None,
            blockers=(
                "PREDICTION_OUTCOME_IDENTITY_MISMATCH",
            ),
        )

    if prediction.predicted_action == "WAIT":
        if position is not None:
            return _result(
                prediction=prediction,
                outcome=outcome,
                position=position,
                reconciled_at=at,
                status="BLOCKED",
                identity_matches=True,
                entry_matches=None,
                terminal_matches=None,
                fill_sequence_matches=None,
                quantity_matches=None,
                pnl_matches=None,
                blockers=(
                    "WAIT_PREDICTION_CANNOT_HAVE_POSITION",
                ),
            )
        if outcome.evaluation_status == "UNRESOLVED":
            return _result(
                prediction=prediction,
                outcome=outcome,
                position=None,
                reconciled_at=at,
                status="PENDING",
                identity_matches=True,
                entry_matches=None,
                terminal_matches=None,
                fill_sequence_matches=None,
                quantity_matches=None,
                pnl_matches=None,
                blockers=("WAIT_OUTCOME_UNRESOLVED",),
            )
        if outcome.evaluation_status == "DATA_UNAVAILABLE":
            return _result(
                prediction=prediction,
                outcome=outcome,
                position=None,
                reconciled_at=at,
                status="DATA_UNAVAILABLE",
                identity_matches=True,
                entry_matches=None,
                terminal_matches=None,
                fill_sequence_matches=None,
                quantity_matches=None,
                pnl_matches=None,
                blockers=outcome.blockers,
            )
        return _result(
            prediction=prediction,
            outcome=outcome,
            position=None,
            reconciled_at=at,
            status="RECONCILED",
            identity_matches=True,
            entry_matches=None,
            terminal_matches=None,
            fill_sequence_matches=None,
            quantity_matches=None,
            pnl_matches=None,
        )

    if outcome.evaluation_status == "DATA_UNAVAILABLE":
        return _result(
            prediction=prediction,
            outcome=outcome,
            position=position,
            reconciled_at=at,
            status="DATA_UNAVAILABLE",
            identity_matches=True,
            entry_matches=None,
            terminal_matches=None,
            fill_sequence_matches=None,
            quantity_matches=None,
            pnl_matches=None,
            blockers=outcome.blockers,
        )

    if position is None:
        if outcome.evaluation_status == "UNRESOLVED":
            return _result(
                prediction=prediction,
                outcome=outcome,
                position=None,
                reconciled_at=at,
                status="PENDING",
                identity_matches=True,
                entry_matches=None,
                terminal_matches=None,
                fill_sequence_matches=None,
                quantity_matches=None,
                pnl_matches=None,
                blockers=("LIFECYCLE_OUTCOME_UNRESOLVED",),
            )
        if outcome.outcome in _NO_POSITION_OUTCOMES:
            return _result(
                prediction=prediction,
                outcome=outcome,
                position=None,
                reconciled_at=at,
                status="RECONCILED",
                identity_matches=True,
                entry_matches=True,
                terminal_matches=True,
                fill_sequence_matches=True,
                quantity_matches=True,
                pnl_matches=True,
            )
        return _result(
            prediction=prediction,
            outcome=outcome,
            position=None,
            reconciled_at=at,
            status="BLOCKED",
            identity_matches=True,
            entry_matches=None,
            terminal_matches=None,
            fill_sequence_matches=None,
            quantity_matches=None,
            pnl_matches=None,
            blockers=("POSITION_REQUIRED_FOR_OUTCOME",),
        )

    if not _position_identity(prediction, position):
        return _result(
            prediction=prediction,
            outcome=outcome,
            position=position,
            reconciled_at=at,
            status="BLOCKED",
            identity_matches=False,
            entry_matches=None,
            terminal_matches=None,
            fill_sequence_matches=None,
            quantity_matches=None,
            pnl_matches=None,
            blockers=("PREDICTION_POSITION_IDENTITY_MISMATCH",),
        )

    if outcome.outcome in _NO_POSITION_OUTCOMES:
        return _result(
            prediction=prediction,
            outcome=outcome,
            position=position,
            reconciled_at=at,
            status="BLOCKED",
            identity_matches=True,
            entry_matches=False,
            terminal_matches=False,
            fill_sequence_matches=None,
            quantity_matches=None,
            pnl_matches=None,
            blockers=(
                "NO_ENTRY_OUTCOME_CONFLICTS_WITH_POSITION",
            ),
        )

    sequence_matches, quantity_matches, pnl_matches, fills = (
        _fill_checks(position)
    )
    entry_matches = (
        outcome.entry_occurred
        and outcome.entry_at == position.opened_at
        and outcome.entry_premium is not None
        and _close(
            outcome.entry_premium,
            position.entry_price,
        )
    )

    terminal = (
        position.lifecycle_state.startswith("CLOSED_")
        or position.lifecycle_state == "CANCELLED"
    )

    if outcome.evaluation_status == "UNRESOLVED":
        if terminal:
            return _result(
                prediction=prediction,
                outcome=outcome,
                position=position,
                reconciled_at=at,
                status="BLOCKED",
                identity_matches=True,
                entry_matches=entry_matches,
                terminal_matches=False,
                fill_sequence_matches=sequence_matches,
                quantity_matches=quantity_matches,
                pnl_matches=pnl_matches,
                blockers=(
                    "TERMINAL_POSITION_WITH_UNRESOLVED_OUTCOME",
                ),
            )
        blockers = []
        if not entry_matches:
            blockers.append("ENTRY_EVIDENCE_MISMATCH")
        if not sequence_matches:
            blockers.append("FILL_SEQUENCE_MISMATCH")
        if not quantity_matches:
            blockers.append("QUANTITY_MISMATCH")
        if not pnl_matches:
            blockers.append("PNL_MISMATCH")
        if blockers:
            return _result(
                prediction=prediction,
                outcome=outcome,
                position=position,
                reconciled_at=at,
                status="BLOCKED",
                identity_matches=True,
                entry_matches=entry_matches,
                terminal_matches=None,
                fill_sequence_matches=sequence_matches,
                quantity_matches=quantity_matches,
                pnl_matches=pnl_matches,
                blockers=tuple(blockers),
            )
        return _result(
            prediction=prediction,
            outcome=outcome,
            position=position,
            reconciled_at=at,
            status="PENDING",
            identity_matches=True,
            entry_matches=True,
            terminal_matches=None,
            fill_sequence_matches=True,
            quantity_matches=True,
            pnl_matches=True,
            blockers=("POSITION_AND_OUTCOME_REMAIN_OPEN",),
        )

    terminal_matches = _terminal_matches(
        outcome=outcome,
        position=position,
        fills=fills,
    )
    blockers = []
    if not entry_matches:
        blockers.append("ENTRY_EVIDENCE_MISMATCH")
    if not terminal_matches:
        blockers.append("TERMINAL_OUTCOME_MISMATCH")
    if not sequence_matches:
        blockers.append("FILL_SEQUENCE_MISMATCH")
    if not quantity_matches:
        blockers.append("QUANTITY_MISMATCH")
    if not pnl_matches:
        blockers.append("PNL_MISMATCH")

    if blockers:
        return _result(
            prediction=prediction,
            outcome=outcome,
            position=position,
            reconciled_at=at,
            status="BLOCKED",
            identity_matches=True,
            entry_matches=entry_matches,
            terminal_matches=terminal_matches,
            fill_sequence_matches=sequence_matches,
            quantity_matches=quantity_matches,
            pnl_matches=pnl_matches,
            blockers=tuple(blockers),
        )

    return _result(
        prediction=prediction,
        outcome=outcome,
        position=position,
        reconciled_at=at,
        status="RECONCILED",
        identity_matches=True,
        entry_matches=True,
        terminal_matches=True,
        fill_sequence_matches=True,
        quantity_matches=True,
        pnl_matches=True,
    )

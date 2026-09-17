"""R4.4 position, reservation, and P&L reconciliation certification."""

from dataclasses import replace
from datetime import timedelta

import pytest

from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.paper_orchestration.position_reservation_pnl_reconciliation_runtime import (
    PositionReservationPnlReconciliationResultV1,
    execute_position_reservation_pnl_reconciliation,
)
from tests.test_r42_admitted_plan_simulated_entry_runtime import (
    _admitted_runtime_args,
)


def _open_runtime(tmp_path):
    from services.paper_orchestration.admitted_plan_simulated_entry_runtime import (
        execute_admitted_plan_simulated_entry,
    )

    entry_args, portfolio_service, trade_service = (
        _admitted_runtime_args(tmp_path)
    )

    entry_result = execute_admitted_plan_simulated_entry(
        **entry_args
    )

    assert entry_result.status == "OPEN"

    return (
        entry_args,
        portfolio_service,
        trade_service,
    )


def _reconciliation_args(
    *,
    entry_args,
    portfolio_service,
    trade_service,
    repair_requested,
    suffix,
    reconciled_at=None,
):
    p7 = trade_service.get(entry_args["paper_trade_id"])
    assert p7 is not None

    if reconciled_at is None:
        reconciled_at = p7.updated_at + timedelta(seconds=1)

    return {
        "portfolio_id": entry_args["portfolio_id"],
        "paper_trade_id": entry_args["paper_trade_id"],
        "portfolio_policy": entry_args["portfolio_policy"],
        "reconciled_at": reconciled_at,
        "repair_requested": repair_requested,
        "repair_idempotency_key": (
            f"r44-repair-{suffix}"
        ),
        "result_snapshot_id": (
            f"r44-portfolio-{suffix}"
        ),
        "portfolio_event_id": (
            f"r44-event-{suffix}"
        ),
        "portfolio_persistence_service": (
            portfolio_service
        ),
        "trade_persistence_service": trade_service,
    }


def _persist_drifted_portfolio(
    *,
    portfolio_service,
    transform_snapshot,
):
    current = portfolio_service.get("portfolio-1")
    assert current is not None

    changed_snapshot = transform_snapshot(
        current.portfolio_snapshot
    )

    drifted = PaperPortfolioPersistenceSnapshotV1(
        portfolio_id=current.portfolio_id,
        portfolio_snapshot=changed_snapshot,
        admission_idempotency_records=dict(
            current.admission_idempotency_records
        ),
        update_idempotency_records=dict(
            current.update_idempotency_records
        ),
        processed_portfolio_event_hashes=dict(
            current.processed_portfolio_event_hashes
        ),
        processed_p7_transition_hashes=dict(
            current.processed_p7_transition_hashes
        ),
        processed_p7_fill_hashes=dict(
            current.processed_p7_fill_hashes
        ),
        created_at=current.created_at,
        updated_at=changed_snapshot.updated_at,
        event_sequence=changed_snapshot.event_sequence,
    )

    portfolio_service.save(drifted)
    return drifted


def test_consistent_state_is_reconciled_without_mutation(
    tmp_path,
):
    (
        entry_args,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    before = portfolio_service.get(
        entry_args["portfolio_id"]
    )
    assert before is not None

    result = (
        execute_position_reservation_pnl_reconciliation(
            **_reconciliation_args(
                entry_args=entry_args,
                portfolio_service=portfolio_service,
                trade_service=trade_service,
                repair_requested=False,
                suffix="consistent",
            )
        )
    )

    assert (
        type(result)
        is PositionReservationPnlReconciliationResultV1
    )
    assert result.status == "RECONCILED"
    assert result.drift_codes == ()
    assert result.state_changed is False
    assert result.idempotent_replay is False

    assert (
        portfolio_service.get(entry_args["portfolio_id"])
        == before
    )


def test_quantity_drift_is_detected_without_repair(
    tmp_path,
):
    (
        entry_args,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    current = portfolio_service.get(
        entry_args["portfolio_id"]
    )
    assert current is not None

    reference = (
        current.portfolio_snapshot.position_references[0]
    )
    position = trade_service.get(
        entry_args["paper_trade_id"]
    ).position
    assert position is not None

    altered_reference = replace(
        reference,
        remaining_lot_count=(
            reference.remaining_lot_count - 1
        ),
        remaining_quantity=(
            reference.remaining_quantity
            - reference.lot_size
        ),
        remaining_capital_amount=(
            reference.remaining_capital_amount
            * (
                (
                    reference.remaining_quantity
                    - reference.lot_size
                )
                / reference.initial_quantity
            )
        ),
        remaining_risk_amount=(
            reference.remaining_risk_amount
            * (
                (
                    reference.remaining_quantity
                    - reference.lot_size
                )
                / reference.initial_quantity
            )
        ),
    )

    drifted_snapshot = replace(
        current.portfolio_snapshot,
        position_references=(altered_reference,),
        updated_at=current.updated_at + timedelta(seconds=1),
    )

    _persist_drifted_portfolio(
        portfolio_service=portfolio_service,
        transform_snapshot=lambda _: drifted_snapshot,
    )

    before = portfolio_service.get(
        entry_args["portfolio_id"]
    )

    result = (
        execute_position_reservation_pnl_reconciliation(
            **_reconciliation_args(
                entry_args=entry_args,
                portfolio_service=portfolio_service,
                trade_service=trade_service,
                repair_requested=False,
                suffix="quantity-detect",
                reconciled_at=(
                    drifted_snapshot.updated_at
                    + timedelta(seconds=1)
                ),
            )
        )
    )

    assert result.status == "DRIFT_DETECTED"
    assert result.state_changed is False
    assert (
        "P7_QUANTITY_MISMATCH"
        in result.drift_codes
        or "POSITION_REFERENCE_QUANTITY_MISMATCH"
        in result.drift_codes
    )

    assert (
        portfolio_service.get(entry_args["portfolio_id"])
        == before
    )


def test_explicit_repair_restores_reference_and_reservation(
    tmp_path,
):
    (
        entry_args,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    current = portfolio_service.get(
        entry_args["portfolio_id"]
    )
    assert current is not None

    reservation = current.portfolio_snapshot.reservations[0]
    reference = (
        current.portfolio_snapshot.position_references[0]
    )

    altered_reservation = replace(
        reservation,
        last_p7_transition_sequence=0,
    )
    altered_reference = replace(
        reference,
        transition_sequence=0,
        last_observation_id="wrong-observation",
    )

    drifted_snapshot = replace(
        current.portfolio_snapshot,
        reservations=(altered_reservation,),
        position_references=(altered_reference,),
        updated_at=current.updated_at + timedelta(seconds=1),
    )

    _persist_drifted_portfolio(
        portfolio_service=portfolio_service,
        transform_snapshot=lambda _: drifted_snapshot,
    )

    result = (
        execute_position_reservation_pnl_reconciliation(
            **_reconciliation_args(
                entry_args=entry_args,
                portfolio_service=portfolio_service,
                trade_service=trade_service,
                repair_requested=True,
                suffix="repair",
                reconciled_at=(
                    drifted_snapshot.updated_at
                    + timedelta(seconds=1)
                ),
            )
        )
    )

    assert result.status == "REPAIRED"
    assert result.drift_codes == ()
    assert result.state_changed is True
    assert result.idempotent_replay is False

    persisted_p7 = trade_service.get(
        entry_args["paper_trade_id"]
    )
    persisted_p8 = portfolio_service.get(
        entry_args["portfolio_id"]
    )

    assert persisted_p7 is not None
    assert persisted_p7.position is not None
    assert persisted_p8 is not None

    repaired_reservation = (
        persisted_p8.portfolio_snapshot.reservations[0]
    )
    repaired_reference = (
        persisted_p8.portfolio_snapshot.position_references[0]
    )

    assert (
        repaired_reservation.last_p7_transition_sequence
        == persisted_p7.event_sequence
    )
    assert (
        repaired_reference.transition_sequence
        == persisted_p7.event_sequence
    )
    assert (
        repaired_reference.last_observation_id
        == persisted_p7.latest_observation.observation_id
    )
    assert (
        repaired_reference.remaining_quantity
        == persisted_p7.position.remaining_quantity
    )
    assert (
        repaired_reference.realized_net_pnl
        == persisted_p7.position.realized_net_pnl
    )
    assert (
        repaired_reference.unrealized_pnl
        == persisted_p7.position.unrealized_pnl
    )
    assert (
        repaired_reference.total_pnl
        == persisted_p7.position.total_pnl
    )


def test_repair_exact_replay_is_idempotent(tmp_path):
    (
        entry_args,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    current = portfolio_service.get(
        entry_args["portfolio_id"]
    )
    assert current is not None

    reservation = current.portfolio_snapshot.reservations[0]
    reference = (
        current.portfolio_snapshot.position_references[0]
    )

    altered_reservation = replace(
        reservation,
        last_p7_transition_sequence=0,
    )
    altered_reference = replace(
        reference,
        transition_sequence=0,
    )

    drifted_snapshot = replace(
        current.portfolio_snapshot,
        reservations=(altered_reservation,),
        position_references=(altered_reference,),
        updated_at=current.updated_at + timedelta(seconds=1),
    )

    _persist_drifted_portfolio(
        portfolio_service=portfolio_service,
        transform_snapshot=lambda _: drifted_snapshot,
    )

    args = _reconciliation_args(
        entry_args=entry_args,
        portfolio_service=portfolio_service,
        trade_service=trade_service,
        repair_requested=True,
        suffix="replay",
        reconciled_at=(
            drifted_snapshot.updated_at
            + timedelta(seconds=1)
        ),
    )

    first = execute_position_reservation_pnl_reconciliation(
        **args
    )

    before = portfolio_service.get(
        entry_args["portfolio_id"]
    )

    second = execute_position_reservation_pnl_reconciliation(
        **args
    )

    assert first.status == "REPAIRED"
    assert second.status == "REPAIRED"
    assert second.state_changed is False
    assert second.idempotent_replay is True

    assert (
        portfolio_service.get(entry_args["portfolio_id"])
        == before
    )


def test_changed_repair_payload_fails_closed(tmp_path):
    (
        entry_args,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    current = portfolio_service.get(
        entry_args["portfolio_id"]
    )
    assert current is not None

    reservation = current.portfolio_snapshot.reservations[0]
    reference = (
        current.portfolio_snapshot.position_references[0]
    )

    altered_reservation = replace(
        reservation,
        last_p7_transition_sequence=0,
    )
    altered_reference = replace(
        reference,
        transition_sequence=0,
    )

    drifted_snapshot = replace(
        current.portfolio_snapshot,
        reservations=(altered_reservation,),
        position_references=(altered_reference,),
        updated_at=current.updated_at + timedelta(seconds=1),
    )

    _persist_drifted_portfolio(
        portfolio_service=portfolio_service,
        transform_snapshot=lambda _: drifted_snapshot,
    )

    args = _reconciliation_args(
        entry_args=entry_args,
        portfolio_service=portfolio_service,
        trade_service=trade_service,
        repair_requested=True,
        suffix="conflict",
        reconciled_at=(
            drifted_snapshot.updated_at
            + timedelta(seconds=1)
        ),
    )

    execute_position_reservation_pnl_reconciliation(
        **args
    )

    before = portfolio_service.get(
        entry_args["portfolio_id"]
    )

    with pytest.raises(
        ValueError,
        match="IDEMPOTENCY_PAYLOAD_CONFLICT",
    ):
        execute_position_reservation_pnl_reconciliation(
            **(
                args
                | {
                    "paper_trade_id": "different-trade",
                }
            )
        )

    assert (
        portfolio_service.get(entry_args["portfolio_id"])
        == before
    )


def test_submission_guard_rejects_without_mutation(
    tmp_path,
):
    (
        entry_args,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    before = portfolio_service.get(
        entry_args["portfolio_id"]
    )

    with pytest.raises(
        ValueError,
        match="order submission must remain disabled",
    ):
        execute_position_reservation_pnl_reconciliation(
            **_reconciliation_args(
                entry_args=entry_args,
                portfolio_service=portfolio_service,
                trade_service=trade_service,
                repair_requested=False,
                suffix="submission",
            ),
            broker_order_submission=True,
        )

    assert (
        portfolio_service.get(entry_args["portfolio_id"])
        == before
    )
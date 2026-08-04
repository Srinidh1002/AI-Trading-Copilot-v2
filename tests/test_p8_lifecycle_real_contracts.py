from __future__ import annotations

import math

from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    PaperPortfolioLifecycleCoordinator,
)
from tests.p8_portfolio_harness import (
    PORTFOLIO_ID,
    NOW,
    make_open_p7_snapshot,
    make_p8_policy,
    make_persistence_service,
    make_position_update_result,
    make_p7_snapshot_from_result,
)


def test_open_activation_moves_pending_to_deployed(tmp_path):
    service = make_persistence_service(tmp_path)
    coordinator = PaperPortfolioLifecycleCoordinator(service)

    after = coordinator.apply_p7_snapshot(
        portfolio_id=PORTFOLIO_ID,
        policy=make_p8_policy(),
        p7_snapshot=make_open_p7_snapshot(),
        result_snapshot_id="p8-snapshot-open",
        portfolio_event_id="p8-event-open",
        update_idempotency_key="p8-update-open",
        updated_at=NOW,
    )

    snapshot = after.portfolio_snapshot
    assert snapshot.reserved_capital == 0.0
    assert snapshot.deployed_capital == 5000.0
    assert snapshot.committed_capital == 5000.0
    assert snapshot.pending_plan_count == 0
    assert snapshot.open_position_count == 1
    assert snapshot.concurrent_trade_count == 1
    assert snapshot.reservations[0].reservation_status == "ACTIVE"
    assert snapshot.position_references[0].lifecycle_state == "OPEN"


def test_duplicate_open_replay_is_no_change(tmp_path):
    service = make_persistence_service(tmp_path)
    coordinator = PaperPortfolioLifecycleCoordinator(service)
    p7 = make_open_p7_snapshot()

    first = coordinator.apply_p7_snapshot(
        portfolio_id=PORTFOLIO_ID,
        policy=make_p8_policy(),
        p7_snapshot=p7,
        result_snapshot_id="p8-snapshot-open",
        portfolio_event_id="p8-event-open",
        update_idempotency_key="p8-update-open",
        updated_at=NOW,
    )
    second = coordinator.apply_p7_snapshot(
        portfolio_id=PORTFOLIO_ID,
        policy=make_p8_policy(),
        p7_snapshot=p7,
        result_snapshot_id="ignored-duplicate-id",
        portfolio_event_id="ignored-duplicate-event",
        update_idempotency_key="p8-update-open",
        updated_at=NOW,
    )

    assert second.to_json() == first.to_json()
    assert second.event_sequence == first.event_sequence


def test_t1_partial_release_scales_from_original(tmp_path):
    service = make_persistence_service(tmp_path)
    coordinator = PaperPortfolioLifecycleCoordinator(service)

    coordinator.apply_p7_snapshot(
        portfolio_id=PORTFOLIO_ID,
        policy=make_p8_policy(),
        p7_snapshot=make_open_p7_snapshot(),
        result_snapshot_id="p8-snapshot-open",
        portfolio_event_id="p8-event-open",
        update_idempotency_key="p8-update-open",
        updated_at=NOW,
    )

    evaluation_input, result = make_position_update_result(
        option_price=110.0,
        result_id="partial",
        transition_id="transition-partial",
    )
    assert result.status == "PARTIALLY_EXITED"
    p7_partial = make_p7_snapshot_from_result(
        result=result,
        observation=evaluation_input.observation,
        paper_trade_id="paper-trade-1",
        key="p7-partial-key",
        payload_hash="p7-partial-hash",
        event_sequence=2,
    )

    after = coordinator.apply_p7_snapshot(
        portfolio_id=PORTFOLIO_ID,
        policy=make_p8_policy(),
        p7_snapshot=p7_partial,
        result_snapshot_id="p8-snapshot-partial",
        portfolio_event_id="p8-event-partial",
        update_idempotency_key="p8-update-partial",
        updated_at=NOW,
    )

    reservation = after.portfolio_snapshot.reservations[0]
    expected = reservation.original_capital_amount * (
        reservation.remaining_quantity / reservation.initial_quantity
    )
    assert reservation.reservation_status == "ACTIVE"
    assert math.isclose(reservation.remaining_capital_amount, expected, abs_tol=1e-9)
    assert reservation.released_capital_amount > 0.0
    assert after.portfolio_snapshot.position_references[0].lifecycle_state == "PARTIALLY_EXITED"


def test_stop_terminal_release_zeroes_capacity_and_keeps_realized_pnl(tmp_path):
    service = make_persistence_service(tmp_path)
    coordinator = PaperPortfolioLifecycleCoordinator(service)

    coordinator.apply_p7_snapshot(
        portfolio_id=PORTFOLIO_ID,
        policy=make_p8_policy(),
        p7_snapshot=make_open_p7_snapshot(),
        result_snapshot_id="p8-snapshot-open",
        portfolio_event_id="p8-event-open",
        update_idempotency_key="p8-update-open",
        updated_at=NOW,
    )

    evaluation_input, result = make_position_update_result(
        option_price=90.0,
        result_id="stop",
        transition_id="transition-stop",
    )
    assert result.status == "CLOSED_STOP"
    p7_terminal = make_p7_snapshot_from_result(
        result=result,
        observation=evaluation_input.observation,
        paper_trade_id="paper-trade-1",
        key="p7-stop-key",
        payload_hash="p7-stop-hash",
        event_sequence=2,
    )

    after = coordinator.apply_p7_snapshot(
        portfolio_id=PORTFOLIO_ID,
        policy=make_p8_policy(),
        p7_snapshot=p7_terminal,
        result_snapshot_id="p8-snapshot-stop",
        portfolio_event_id="p8-event-stop",
        update_idempotency_key="p8-update-stop",
        updated_at=NOW,
    )

    snapshot = after.portfolio_snapshot
    reservation = snapshot.reservations[0]
    reference = snapshot.position_references[0]

    assert reservation.reservation_status == "RELEASED"
    assert reservation.remaining_capital_amount == 0.0
    assert reservation.remaining_risk_amount == 0.0
    assert snapshot.deployed_capital == 0.0
    assert snapshot.committed_capital == 0.0
    assert snapshot.open_position_count == 0
    assert reference.is_terminal
    assert reference.unrealized_pnl == 0.0
    assert snapshot.realized_net_pnl == reference.realized_net_pnl
    assert snapshot.total_pnl == snapshot.realized_net_pnl

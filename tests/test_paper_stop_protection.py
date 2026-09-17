"""Task 5 Slice 8 protected-stop policy certification."""
from datetime import datetime, timedelta, timezone

import pytest

from services.contracts.active_paper_position_v1 import (
    ActivePaperPositionV1,
)
from services.contracts.paper_monitoring_lifecycle_v1 import (
    PaperLifecycleTransitionV1,
)
from services.paper_trading.json_paper_position_repository import (
    JsonPaperPositionRepository,
)
from services.paper_trading.paper_stop_protection import (
    apply_move_stop_transition,
    build_move_stop_transition,
)


NOW = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)


def position(**changes):
    values = dict(
        position_id="position-1",
        recommendation_id="recommendation-1",
        reservation_result_id="reservation-1",
        fill_result_id="fill-1",
        opened_at=NOW - timedelta(minutes=10),
        updated_at=NOW - timedelta(seconds=1),
        underlying_symbol="NIFTY",
        exchange="NSE",
        option_right="CALL",
        contract="NIFTY06AUG26C25000",
        expiry="2026-08-06",
        strike=25000.0,
        entry_price=100.0,
        stop_loss=90.0,
        target_1=110.0,
        target_2=120.0,
        target_3=130.0,
        initial_lots=3,
        remaining_lots=2,
        lot_size=25,
        initial_quantity=75,
        remaining_quantity=50,
        reserved_capital=7600.0,
        maximum_loss=1000.0,
        lifecycle_state="PARTIALLY_EXITED",
        target_1_hit=True,
    )
    values.update(changes)
    return ActivePaperPositionV1(**values)


def build(p=None, **changes):
    values = dict(
        transition_id="move-stop-1",
        evidence_id="evidence-1",
        evaluated_at=NOW,
        position=p or position(),
    )
    values.update(changes)
    return build_move_stop_transition(**values)


def test_target_one_builds_breakeven_stop():
    result = build()

    assert result.action == "MOVE_STOP"
    assert result.effective_stop_loss == 100.0
    assert result.remaining_quantity == 50
    assert result.reasons == (
        "MOVE_TO_BREAKEVEN_AFTER_TARGET_1",
    )


def test_target_two_builds_target_one_protected_stop():
    current = position(
        remaining_lots=1,
        remaining_quantity=25,
        target_2_hit=True,
        current_stop_loss=100.0,
    )

    result = build(current)

    assert result.effective_stop_loss == 110.0
    assert result.reasons == ("PROTECT_AFTER_TARGET_2",)


def test_stop_movement_is_persisted(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position()
    repository.save(current)
    transition = build(current)

    updated = apply_move_stop_transition(
        position=current,
        transition=transition,
        repository=repository,
    )

    assert updated.current_stop_loss == 100.0
    assert updated.processed_event_ids == ("move-stop-1",)
    assert repository.get("position-1") == updated


def test_duplicate_stop_transition_is_idempotent(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position()
    repository.save(current)
    transition = build(current)

    first = apply_move_stop_transition(
        position=current,
        transition=transition,
        repository=repository,
    )
    second = apply_move_stop_transition(
        position=first,
        transition=transition,
        repository=repository,
    )

    assert second == first


def test_stop_never_moves_backward(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position(current_stop_loss=100.0)
    repository.save(current)
    transition = PaperLifecycleTransitionV1(
        transition_id="move-stop-2",
        position_id=current.position_id,
        evidence_id="evidence-2",
        evaluated_at=NOW,
        action="MOVE_STOP",
        previous_state=current.lifecycle_state,
        next_state=current.lifecycle_state,
        exit_quantity=0,
        remaining_quantity=current.remaining_quantity,
        effective_stop_loss=99.0,
        reasons=("INVALID_BACKWARD_MOVE",),
    )

    with pytest.raises(ValueError, match="move forward"):
        apply_move_stop_transition(
            position=current,
            transition=transition,
            repository=repository,
        )


def test_stop_requires_target_milestone():
    current = position(
        lifecycle_state="OPEN",
        remaining_lots=3,
        remaining_quantity=75,
        target_1_hit=False,
    )

    with pytest.raises(ValueError, match="milestone"):
        build(current)


def test_already_protected_stop_does_not_emit_duplicate_move():
    current = position(current_stop_loss=100.0)

    with pytest.raises(ValueError, match="already protected"):
        build(current)


def test_target_two_policy_floor_is_enforced(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position(
        remaining_lots=1,
        remaining_quantity=25,
        target_2_hit=True,
        current_stop_loss=100.0,
    )
    repository.save(current)
    transition = PaperLifecycleTransitionV1(
        transition_id="move-stop-2",
        position_id=current.position_id,
        evidence_id="evidence-2",
        evaluated_at=NOW,
        action="MOVE_STOP",
        previous_state=current.lifecycle_state,
        next_state=current.lifecycle_state,
        exit_quantity=0,
        remaining_quantity=current.remaining_quantity,
        effective_stop_loss=105.0,
        reasons=("INVALID_POLICY_MOVE",),
    )

    with pytest.raises(ValueError, match="policy floor"):
        apply_move_stop_transition(
            position=current,
            transition=transition,
            repository=repository,
        )


def test_non_move_stop_and_identity_mismatch_are_rejected(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position()
    repository.save(current)
    transition = build(current)

    with pytest.raises(ValueError, match="unsupported"):
        apply_move_stop_transition(
            position=current,
            transition=PaperLifecycleTransitionV1(
                transition_id="hold-1",
                position_id=current.position_id,
                evidence_id="evidence-1",
                evaluated_at=NOW,
                action="HOLD",
                previous_state=current.lifecycle_state,
                next_state=current.lifecycle_state,
                exit_quantity=0,
                remaining_quantity=current.remaining_quantity,
                effective_stop_loss=current.current_stop_loss,
                reasons=("SETUP_REMAINS_VALID",),
            ),
            repository=repository,
        )

    with pytest.raises(ValueError, match="mismatch"):
        apply_move_stop_transition(
            position=current,
            transition=PaperLifecycleTransitionV1(
                transition_id=transition.transition_id,
                position_id="position-2",
                evidence_id=transition.evidence_id,
                evaluated_at=transition.evaluated_at,
                action=transition.action,
                previous_state=transition.previous_state,
                next_state=transition.next_state,
                exit_quantity=transition.exit_quantity,
                remaining_quantity=transition.remaining_quantity,
                effective_stop_loss=transition.effective_stop_loss,
                reasons=transition.reasons,
            ),
            repository=repository,
        )


def test_protected_stop_survives_restart(tmp_path):
    path = tmp_path / "positions.json"
    repository = JsonPaperPositionRepository(path)
    current = position()
    repository.save(current)
    transition = build(current)
    apply_move_stop_transition(
        position=current,
        transition=transition,
        repository=repository,
    )

    restarted = JsonPaperPositionRepository(path)
    recovered = restarted.get("position-1")

    assert recovered is not None
    assert recovered.current_stop_loss == 100.0

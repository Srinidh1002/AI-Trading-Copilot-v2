"""Task 5 Slice 7 persistent target-exit certification."""
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
from services.paper_trading.paper_target_transition_applier import (
    apply_target_transition,
)


NOW = datetime(2026, 8, 3, 9, 55, tzinfo=timezone.utc)


def position(**changes):
    values = dict(
        position_id="position-1",
        recommendation_id="recommendation-1",
        reservation_result_id="reservation-1",
        fill_result_id="fill-1",
        opened_at=NOW - timedelta(minutes=5),
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
        remaining_lots=3,
        lot_size=25,
        initial_quantity=75,
        remaining_quantity=75,
        reserved_capital=7600.0,
        maximum_loss=1000.0,
    )
    values.update(changes)
    return ActivePaperPositionV1(**values)


def transition(**changes):
    values = dict(
        transition_id="transition-t1",
        position_id="position-1",
        evidence_id="evidence-1",
        evaluated_at=NOW,
        action="TARGET_1_HIT",
        previous_state="OPEN",
        next_state="PARTIALLY_EXITED",
        exit_quantity=25,
        remaining_quantity=50,
        effective_stop_loss=90.0,
        reasons=("TARGET_1_REACHED",),
    )
    values.update(changes)
    return PaperLifecycleTransitionV1(**values)


def apply(repository, p=None, t=None):
    return apply_target_transition(
        position=p or position(),
        transition=t or transition(),
        repository=repository,
    )


def test_target_one_partial_exit_is_persisted(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)

    updated = apply(repository)

    assert updated.lifecycle_state == "PARTIALLY_EXITED"
    assert updated.target_1_hit is True
    assert updated.remaining_lots == 2
    assert updated.remaining_quantity == 50
    assert updated.realized_pnl == 250.0
    assert updated.processed_event_ids == ("transition-t1",)
    assert repository.get("position-1") == updated


def test_target_two_partial_exit_accumulates_pnl(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position(
        lifecycle_state="PARTIALLY_EXITED",
        remaining_lots=2,
        remaining_quantity=50,
        target_1_hit=True,
        realized_pnl=250.0,
        processed_event_ids=("transition-t1",),
    )
    repository.save(current)

    updated = apply(
        repository,
        p=current,
        t=transition(
            transition_id="transition-t2",
            action="TARGET_2_HIT",
            previous_state="PARTIALLY_EXITED",
            exit_quantity=25,
            remaining_quantity=25,
            reasons=("TARGET_2_REACHED",),
        ),
    )

    assert updated.target_1_hit is True
    assert updated.target_2_hit is True
    assert updated.target_3_hit is False
    assert updated.remaining_lots == 1
    assert updated.realized_pnl == 750.0


def test_target_three_closes_remaining_position(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position(
        lifecycle_state="PARTIALLY_EXITED",
        remaining_lots=1,
        remaining_quantity=25,
        target_1_hit=True,
        target_2_hit=True,
        realized_pnl=750.0,
        processed_event_ids=("transition-t1", "transition-t2"),
    )
    repository.save(current)

    updated = apply(
        repository,
        p=current,
        t=transition(
            transition_id="transition-t3",
            action="TARGET_3_HIT",
            previous_state="PARTIALLY_EXITED",
            next_state="CLOSED",
            exit_quantity=25,
            remaining_quantity=0,
            reasons=("TARGET_3_REACHED",),
        ),
    )

    assert updated.lifecycle_state == "CLOSED"
    assert updated.target_3_hit is True
    assert updated.remaining_lots == 0
    assert updated.remaining_quantity == 0
    assert updated.realized_pnl == 1500.0
    assert repository.list_active() == ()


def test_duplicate_target_transition_is_idempotent(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    repository.save(position())

    first = apply(repository)
    second = apply(repository, p=first)

    assert second == first
    assert second.realized_pnl == 250.0


def test_target_ordering_is_enforced(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)

    with pytest.raises(ValueError, match="TARGET_2 requires"):
        apply(
            repository,
            t=transition(
                action="TARGET_2_HIT",
                reasons=("TARGET_2_REACHED",),
            ),
        )


def test_quantity_and_state_must_match_transition(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)

    with pytest.raises(ValueError, match="whole lots"):
        apply(
            repository,
            t=transition(
                exit_quantity=10,
                remaining_quantity=65,
            ),
        )

    with pytest.raises(ValueError, match="remaining_quantity"):
        apply(
            repository,
            t=transition(remaining_quantity=25),
        )

    with pytest.raises(ValueError, match="next_state"):
        apply(
            repository,
            t=transition(next_state="CLOSED"),
        )


def test_non_target_and_mismatched_transition_rejected(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)

    with pytest.raises(ValueError, match="unsupported"):
        apply(
            repository,
            t=transition(
                action="HOLD",
                exit_quantity=0,
                remaining_quantity=75,
                next_state="OPEN",
                reasons=("SETUP_REMAINS_VALID",),
            ),
        )

    with pytest.raises(ValueError, match="mismatch"):
        apply(
            repository,
            t=transition(position_id="position-2"),
        )


def test_persistence_survives_restart(tmp_path):
    path = tmp_path / "positions.json"
    repository = JsonPaperPositionRepository(path)
    repository.save(position())
    apply(repository)

    restarted = JsonPaperPositionRepository(path)
    recovered = restarted.get("position-1")

    assert recovered is not None
    assert recovered.target_1_hit is True
    assert recovered.remaining_quantity == 50
    assert recovered.realized_pnl == 250.0

"""Task 5 Slice 6 persistent HOLD application certification."""
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
from services.paper_trading.paper_hold_transition_applier import (
    apply_hold_transition,
)


NOW = datetime(2026, 8, 3, 9, 50, tzinfo=timezone.utc)


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
        transition_id="transition-1",
        position_id="position-1",
        evidence_id="evidence-1",
        evaluated_at=NOW,
        action="HOLD",
        previous_state="OPEN",
        next_state="OPEN",
        exit_quantity=0,
        remaining_quantity=75,
        effective_stop_loss=90.0,
        reasons=("SETUP_REMAINS_VALID",),
    )
    values.update(changes)
    return PaperLifecycleTransitionV1(**values)


def apply(repository, p=None, t=None):
    return apply_hold_transition(
        position=p or position(),
        transition=t or transition(),
        repository=repository,
    )


def test_hold_updates_timestamp_and_persists_event(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)

    updated = apply(repository)

    assert updated.updated_at == NOW
    assert updated.lifecycle_state == "OPEN"
    assert updated.remaining_quantity == 75
    assert updated.processed_event_ids == ("transition-1",)
    assert repository.get("position-1") == updated


def test_hold_with_caution_persists_warning(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)

    updated = apply(
        repository,
        t=transition(
            action="HOLD_WITH_CAUTION",
            reasons=("CONFIDENCE_DETERIORATED",),
            warnings=("OPTION_CHAIN_CONTRADICTION",),
        ),
    )

    assert "HOLD_WITH_CAUTION" in updated.warnings
    assert "OPTION_CHAIN_CONTRADICTION" in updated.warnings


def test_duplicate_transition_is_idempotent(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)

    first = apply(repository)
    second = apply(repository, p=first)

    assert second == first
    assert second.processed_event_ids == ("transition-1",)


def test_non_hold_action_is_rejected(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)

    with pytest.raises(ValueError, match="unsupported"):
        apply(
            repository,
            t=transition(
                action="MOVE_STOP",
                reasons=("STOP_POLICY_TRIGGERED",),
            ),
        )


def test_transition_identity_and_state_must_match(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)

    with pytest.raises(ValueError, match="mismatch"):
        apply(
            repository,
            t=transition(position_id="position-2"),
        )

    with pytest.raises(ValueError, match="previous_state"):
        apply(
            repository,
            t=transition(previous_state="PARTIALLY_EXITED"),
        )


def test_hold_cannot_change_quantity_or_state(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)

    with pytest.raises(ValueError, match="lifecycle state"):
        apply(
            repository,
            t=transition(next_state="PARTIALLY_EXITED"),
        )

    with pytest.raises(ValueError, match="remaining_quantity"):
        apply(
            repository,
            t=transition(remaining_quantity=50),
        )


def test_old_transition_is_rejected(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)

    with pytest.raises(ValueError, match="precedes"):
        apply(
            repository,
            t=transition(
                evaluated_at=NOW - timedelta(seconds=2)
            ),
        )


def test_application_survives_repository_restart(tmp_path):
    path = tmp_path / "positions.json"
    repository = JsonPaperPositionRepository(path)
    repository.save(position())
    apply(repository)

    restarted = JsonPaperPositionRepository(path)
    recovered = restarted.get("position-1")

    assert recovered is not None
    assert recovered.processed_event_ids == ("transition-1",)

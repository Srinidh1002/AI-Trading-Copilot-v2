"""Task 5 Slice 9 stop and safety exit certification."""
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
from services.paper_trading.paper_terminal_exit_applier import (
    apply_terminal_exit_transition,
)


NOW = datetime(2026, 8, 3, 10, 5, tzinfo=timezone.utc)


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
        transition_id="exit-1",
        position_id="position-1",
        evidence_id="evidence-1",
        evaluated_at=NOW,
        action="STOP_HIT",
        previous_state="OPEN",
        next_state="CLOSED",
        exit_quantity=75,
        remaining_quantity=0,
        effective_stop_loss=90.0,
        reasons=("CURRENT_BID_AT_OR_BELOW_STOP",),
    )
    values.update(changes)
    return PaperLifecycleTransitionV1(**values)


def apply(repository, p=None, t=None, exit_price=89.0):
    return apply_terminal_exit_transition(
        position=p or position(),
        transition=t or transition(),
        exit_price=exit_price,
        repository=repository,
    )


def test_stop_hit_closes_full_position(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position()
    repository.save(current)

    updated = apply(repository)

    assert updated.lifecycle_state == "CLOSED"
    assert updated.remaining_lots == 0
    assert updated.remaining_quantity == 0
    assert updated.realized_pnl == -825.0
    assert "STOP_EXIT" in updated.warnings
    assert repository.list_active() == ()


def test_early_safety_exit_closes_remaining_position(tmp_path):
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
    )
    repository.save(current)

    updated = apply(
        repository,
        p=current,
        t=transition(
            action="EXIT_NOW",
            previous_state="PARTIALLY_EXITED",
            exit_quantity=25,
            reasons=("SETUP_INVALIDATED",),
        ),
        exit_price=115.0,
    )

    assert updated.lifecycle_state == "CLOSED"
    assert updated.realized_pnl == 1125.0
    assert "EARLY_SAFETY_EXIT" in updated.warnings


def test_duplicate_terminal_exit_is_idempotent(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position()
    repository.save(current)
    event = transition()

    first = apply(
        repository,
        p=current,
        t=event,
    )
    second = apply(
        repository,
        p=first,
        t=event,
    )

    assert second == first
    assert second.realized_pnl == -825.0


def test_terminal_exit_requires_full_remaining_quantity(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position()
    repository.save(current)

    with pytest.raises(ValueError, match="quantity mismatch"):
        apply(
            repository,
            t=transition(
                exit_quantity=50,
                remaining_quantity=25,
            ),
        )


def test_terminal_exit_requires_closed_next_state(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position()
    repository.save(current)

    with pytest.raises(ValueError, match="must close"):
        apply(
            repository,
            t=transition(
                next_state="OPEN",
                exit_quantity=75,
                remaining_quantity=0,
            ),
        )


def test_non_terminal_action_and_identity_mismatch_rejected(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position()
    repository.save(current)

    with pytest.raises(ValueError, match="unsupported"):
        apply(
            repository,
            t=transition(
                action="TARGET_3_HIT",
                reasons=("TARGET_3_REACHED",),
            ),
        )

    with pytest.raises(ValueError, match="mismatch"):
        apply(
            repository,
            t=transition(position_id="position-2"),
        )


def test_invalid_exit_price_rejected(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    current = position()
    repository.save(current)

    with pytest.raises(ValueError, match="exit_price"):
        apply(repository, exit_price=0.0)


def test_terminal_exit_survives_restart(tmp_path):
    path = tmp_path / "positions.json"
    repository = JsonPaperPositionRepository(path)
    current = position()
    repository.save(current)
    apply(repository)

    restarted = JsonPaperPositionRepository(path)
    recovered = restarted.get("position-1")

    assert recovered is not None
    assert recovered.lifecycle_state == "CLOSED"
    assert recovered.remaining_quantity == 0
    assert recovered.realized_pnl == -825.0

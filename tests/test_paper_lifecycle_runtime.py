"""Task 5 Slice 11 end-to-end PAPER lifecycle runtime certification."""
from datetime import datetime, timedelta, timezone

from services.contracts.active_paper_position_v1 import ActivePaperPositionV1
from services.contracts.paper_monitoring_lifecycle_v1 import PaperMonitoringEvidenceV1
from services.paper_trading.json_paper_position_repository import JsonPaperPositionRepository
from services.paper_trading.paper_lifecycle_runtime import run_paper_lifecycle_cycle
from services.paper_trading.paper_trade_finalizer import JsonPaperTradeJournalRepository


NOW = datetime(2026, 8, 3, 10, 15, tzinfo=timezone.utc)


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


def evidence(**changes):
    values = dict(
        evidence_id="evidence-1",
        position_id="position-1",
        observed_at=NOW,
        current_bid=105.0,
        current_ask=106.0,
        current_last=105.5,
        confidence=0.8,
        setup_valid=True,
    )
    values.update(changes)
    return PaperMonitoringEvidenceV1(**values)


def run(position_repository, journal_repository, e=None, **changes):
    values = dict(
        runtime_result_id="runtime-result-1",
        runtime_cycle_id="runtime-cycle-1",
        recovery_result_id="recovery-result-1",
        transition_id="transition-1",
        evaluated_at=NOW,
        evidence=e or evidence(),
        position_repository=position_repository,
        journal_repository=journal_repository,
        maximum_position_age_seconds=60.0,
    )
    values.update(changes)
    return run_paper_lifecycle_cycle(**values)


def repositories(tmp_path):
    return (
        JsonPaperPositionRepository(tmp_path / "positions.json"),
        JsonPaperTradeJournalRepository(tmp_path / "journal.json"),
    )


def test_no_active_position_is_reported(tmp_path):
    positions, journal = repositories(tmp_path)
    result = run(positions, journal)

    assert result.status == "NO_ACTIVE_POSITION"
    assert result.transition is None


def test_hold_is_applied_and_persisted(tmp_path):
    positions, journal = repositories(tmp_path)
    positions.save(position())

    result = run(positions, journal)

    assert result.status == "APPLIED"
    assert result.transition.action == "HOLD"
    assert result.position_after.processed_event_ids == ("transition-1",)
    assert journal.list_all() == ()


def test_target_one_partial_exit_is_applied(tmp_path):
    positions, journal = repositories(tmp_path)
    positions.save(position())

    result = run(
        positions,
        journal,
        e=evidence(current_bid=110.0, current_ask=111.0, current_last=110.5),
    )

    assert result.transition.action == "TARGET_1_HIT"
    assert result.position_after.remaining_quantity == 50
    assert result.position_after.realized_pnl == 250.0


def test_stop_exit_closes_and_finalizes(tmp_path):
    positions, journal = repositories(tmp_path)
    positions.save(position())

    result = run(
        positions,
        journal,
        e=evidence(current_bid=89.0, current_ask=90.0, current_last=89.5),
        closure_id="closure-1",
        journal_entry_id="journal-1",
        finalization_result_id="finalization-1",
    )

    assert result.transition.action == "STOP_HIT"
    assert result.position_after.lifecycle_state == "CLOSED"
    assert result.finalization_result is not None
    assert result.finalization_result.released_capital == 7600.0
    assert len(journal.list_all()) == 1


def test_early_exit_closes_and_finalizes(tmp_path):
    positions, journal = repositories(tmp_path)
    positions.save(position())

    result = run(
        positions,
        journal,
        e=evidence(setup_valid=False),
        closure_id="closure-2",
        journal_entry_id="journal-2",
        finalization_result_id="finalization-2",
    )

    assert result.transition.action == "EXIT_NOW"
    assert result.finalization_result.journal_entry.closure_reason == "EARLY_SAFETY_EXIT"


def test_target_three_finalizes_remaining_position(tmp_path):
    positions, journal = repositories(tmp_path)
    current = position(
        lifecycle_state="PARTIALLY_EXITED",
        remaining_lots=1,
        remaining_quantity=25,
        target_1_hit=True,
        target_2_hit=True,
        realized_pnl=750.0,
        processed_event_ids=("t1", "t2"),
    )
    positions.save(current)

    result = run(
        positions,
        journal,
        e=evidence(current_bid=130.0, current_ask=131.0, current_last=130.5),
        closure_id="closure-3",
        journal_entry_id="journal-3",
        finalization_result_id="finalization-3",
    )

    assert result.transition.action == "TARGET_3_HIT"
    assert result.position_after.realized_pnl == 1500.0
    assert result.finalization_result.journal_entry.closure_reason == "TARGET_3"


def test_recovery_block_prevents_monitoring(tmp_path):
    positions, journal = repositories(tmp_path)
    positions.save(
        position(updated_at=NOW - timedelta(seconds=120))
    )

    result = run(positions, journal)

    assert result.status == "BLOCKED"
    assert result.transition is None


def test_restart_uses_persisted_position(tmp_path):
    positions, journal = repositories(tmp_path)
    positions.save(position())

    restarted_positions = JsonPaperPositionRepository(positions.path)
    result = run(restarted_positions, journal)

    assert result.status == "APPLIED"
    assert result.position_before.position_id == "position-1"

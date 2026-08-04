"""Task 5 Slice 10 closure, release, and journal certification."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from services.contracts.active_paper_position_v1 import (
    ActivePaperPositionV1,
)
from services.paper_trading.paper_trade_finalizer import (
    JsonPaperTradeJournalRepository,
    finalize_closed_paper_trade,
)


NOW = datetime(2026, 8, 3, 10, 10, tzinfo=timezone.utc)


def closed_position(**changes):
    values = dict(
        position_id="position-1",
        recommendation_id="recommendation-1",
        reservation_result_id="reservation-1",
        fill_result_id="fill-1",
        opened_at=NOW - timedelta(minutes=20),
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
        remaining_lots=0,
        lot_size=25,
        initial_quantity=75,
        remaining_quantity=0,
        reserved_capital=7600.0,
        maximum_loss=1000.0,
        lifecycle_state="CLOSED",
        realized_pnl=-825.0,
        processed_event_ids=("stop-event-1",),
        warnings=("STOP_EXIT",),
    )
    values.update(changes)
    return ActivePaperPositionV1(**values)


def finalize(repository, p=None, **changes):
    values = dict(
        finalization_result_id="finalization-1",
        closure_id="closure-1",
        journal_entry_id="journal-1",
        finalized_at=NOW,
        closure_reason="STOP",
        final_exit_price=89.0,
        position=p or closed_position(),
        journal_repository=repository,
    )
    values.update(changes)
    return finalize_closed_paper_trade(**values)


def test_closed_trade_releases_full_capital_and_risk(tmp_path):
    repository = JsonPaperTradeJournalRepository(
        tmp_path / "paper_trade_journal.json"
    )

    result = finalize(repository)

    assert result.status == "FINALIZED"
    assert result.released_capital == 7600.0
    assert result.released_risk == 1000.0
    assert result.journal_entry.realized_pnl == -825.0
    assert result.journal_entry.closure_reason == "STOP"


def test_journal_persists_and_reloads(tmp_path):
    path = tmp_path / "paper_trade_journal.json"
    repository = JsonPaperTradeJournalRepository(path)
    result = finalize(repository)

    restarted = JsonPaperTradeJournalRepository(path)
    assert restarted.list_all() == (result.journal_entry,)
    assert restarted.get_by_closure_id("closure-1") == (
        result.journal_entry
    )


def test_duplicate_finalization_is_idempotent(tmp_path):
    repository = JsonPaperTradeJournalRepository(
        tmp_path / "paper_trade_journal.json"
    )

    first = finalize(repository)
    second = finalize(
        repository,
        finalization_result_id="finalization-2",
        journal_entry_id="journal-2",
    )

    assert second.journal_entry == first.journal_entry
    assert second.released_capital == first.released_capital
    assert second.warnings == (
        "IDEMPOTENT_FINALIZATION_REPLAY",
    )
    assert len(repository.list_all()) == 1


def test_open_position_cannot_be_finalized(tmp_path):
    repository = JsonPaperTradeJournalRepository(
        tmp_path / "paper_trade_journal.json"
    )
    current = closed_position(
        lifecycle_state="OPEN",
        remaining_lots=3,
        remaining_quantity=75,
    )

    with pytest.raises(ValueError, match="must be CLOSED"):
        finalize(repository, p=current)


def test_finalization_time_must_not_precede_position(tmp_path):
    repository = JsonPaperTradeJournalRepository(
        tmp_path / "paper_trade_journal.json"
    )

    with pytest.raises(ValueError, match="precedes"):
        finalize(
            repository,
            finalized_at=NOW - timedelta(seconds=2),
        )


def test_same_position_cannot_be_journaled_twice_with_new_closure(tmp_path):
    repository = JsonPaperTradeJournalRepository(
        tmp_path / "paper_trade_journal.json"
    )
    finalize(repository)

    with pytest.raises(ValueError, match="already journaled"):
        finalize(
            repository,
            closure_id="closure-2",
            journal_entry_id="journal-2",
        )


def test_closure_id_conflict_fails_closed(tmp_path):
    repository = JsonPaperTradeJournalRepository(
        tmp_path / "paper_trade_journal.json"
    )
    finalize(repository)

    other = closed_position(
        position_id="position-2",
        recommendation_id="recommendation-2",
        reservation_result_id="reservation-2",
        fill_result_id="fill-2",
        contract="SENSEX07AUG26P80000",
        underlying_symbol="SENSEX",
        exchange="BSE",
    )

    with pytest.raises(ValueError, match="closure_id conflict"):
        finalize(repository, p=other)


def test_corrupt_journal_fails_closed(tmp_path):
    path = tmp_path / "paper_trade_journal.json"
    path.write_text("{bad-json", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid PAPER"):
        JsonPaperTradeJournalRepository(path).list_all()


def test_atomic_journal_contains_valid_json(tmp_path):
    path = tmp_path / "paper_trade_journal.json"
    repository = JsonPaperTradeJournalRepository(path)
    finalize(repository)

    assert json.loads(path.read_text(encoding="utf-8"))
    assert not path.with_suffix(".json.tmp").exists()

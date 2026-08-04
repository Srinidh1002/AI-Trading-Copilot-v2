from dataclasses import replace
from datetime import datetime, timezone

import pytest

from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)
from services.paper_orchestration.two_market_parent_cycle_journal_adapter import (
    PARENT_CYCLE_JOURNAL_ADAPTER_ID,
    TwoMarketParentCycleJournalAdapter,
    build_parent_cycle_journal_record,
    parent_cycle_semantic_hash,
)
from services.paper_orchestration.authoritative_two_market_entry_point import (
    run_authoritative_two_market_parent_cycle,
)
from test_certified_two_market_parent_runtime import (
    candidate_for,
    cycles,
    parent,
    readers,
)


NOW = datetime(2026, 8, 3, 18, 30, tzinfo=timezone.utc)


def _decision():
    nifty, sensex = cycles()
    parent_input = parent(nifty, sensex)
    runtime_readers = readers(
        lambda cycle, data, analysis, captured, shared_context, *,
        parent_cycle_id: candidate_for(
            cycle,
            data,
            score=80.0
            if cycle.underlying_symbol == "NIFTY"
            else 60.0,
        )
    )
    decision = run_authoritative_two_market_parent_cycle(
        parent_input,
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=runtime_readers,
    )
    return parent_input, decision


def test_record_is_exact_paper_journal_record():
    parent_input, decision = _decision()

    record = build_parent_cycle_journal_record(
        parent=parent_input,
        decision=decision,
        persisted_at=NOW,
    )

    assert record.cycle_idempotency_key == (
        f"two-market-parent:{parent_input.parent_cycle_id}"
    )
    assert record.cycle_result.cycle_id == (
        parent_input.parent_cycle_id
    )
    assert record.cycle_result.cycle_status == (
        "COMPLETED_NO_ACTION"
    )
    assert record.cycle_result.terminal_stage == "OPPORTUNITY"
    assert record.execution_mode == "PAPER"
    assert record.live_execution_eligible is False
    assert (
        record.cycle_result.metadata["adapter_id"]
        == PARENT_CYCLE_JOURNAL_ADAPTER_ID
    )
    assert record.cycle_result.metadata[
        "broker_order_submission"
    ] is False


def test_semantic_hash_is_deterministic():
    parent_input, decision = _decision()

    first = parent_cycle_semantic_hash(
        parent=parent_input,
        decision=decision,
    )
    second = parent_cycle_semantic_hash(
        parent=parent_input,
        decision=decision,
    )

    assert first == second
    assert len(first) == 64


def test_adapter_persists_once_and_duplicate_is_no_change(tmp_path):
    parent_input, decision = _decision()
    journal = PaperOrchestrationJournal(
        tmp_path / "parent-journal.json"
    )
    adapter = TwoMarketParentCycleJournalAdapter(
        journal=journal,
        clock=lambda: NOW,
    )

    first = adapter.persist(
        parent=parent_input,
        decision=decision,
    )
    second = adapter.persist(
        parent=parent_input,
        decision=decision,
    )

    assert first.integrity_hash == second.integrity_hash
    assert journal.count() == 1

    raw = journal.get_raw(first.cycle_idempotency_key)
    assert raw is not None
    assert raw["journal_record_id"] == first.journal_record_id
    assert raw["integrity_hash"] == first.integrity_hash
    assert raw["cycle_result"]["metadata"][
        "decision_result_id"
    ] == decision.decision_result_id


def test_same_parent_key_with_changed_payload_conflicts(tmp_path):
    parent_input, decision = _decision()
    journal = PaperOrchestrationJournal(
        tmp_path / "parent-journal.json"
    )
    adapter = TwoMarketParentCycleJournalAdapter(
        journal=journal,
        clock=lambda: NOW,
    )

    adapter.persist(
        parent=parent_input,
        decision=decision,
    )

    changed = replace(
        decision,
        timestamp_skew_seconds=(
            decision.timestamp_skew_seconds + 1.0
        ),
    )

    with pytest.raises(
        ValueError,
        match="IDEMPOTENCY_PAYLOAD_CONFLICT",
    ):
        adapter.persist(
            parent=parent_input,
            decision=changed,
        )


def test_parent_decision_boundary_mismatch_is_rejected():
    parent_input, decision = _decision()

    changed_parent = replace(
        parent_input,
        decision_result_id="different-decision-result",
    )

    with pytest.raises(
        ValueError,
        match="decision result identity mismatch",
    ):
        build_parent_cycle_journal_record(
            parent=changed_parent,
            decision=decision,
            persisted_at=NOW,
        )


def test_adapter_dependencies_are_exact():
    with pytest.raises(TypeError, match="journal"):
        TwoMarketParentCycleJournalAdapter(
            journal=object(),
            clock=lambda: NOW,
        )

    with pytest.raises(TypeError, match="clock"):
        TwoMarketParentCycleJournalAdapter(
            journal=PaperOrchestrationJournal(),
            clock=object(),
        )



from datetime import datetime, timezone

import pytest

from services.paper_orchestration.authoritative_two_market_entry_point import (
    run_authoritative_two_market_parent_cycle,
)
from services.paper_orchestration.certified_persistence_composition import (
    build_certified_parent_journal_adapter,
    build_certified_persistence_paths,
)
from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)
from services.paper_orchestration.two_market_parent_cycle_journal_adapter import (
    TwoMarketParentCycleJournalAdapter,
)
from test_certified_two_market_parent_runtime import (
    candidate_for,
    cycles,
    parent,
    readers,
)


NOW = datetime(
    2026,
    8,
    4,
    14,
    0,
    tzinfo=timezone.utc,
)


def runtime_inputs():
    nifty, sensex = cycles()
    parent_input = parent(nifty, sensex)
    runtime_readers = readers(
        lambda cycle, data, analysis, captured, shared_context, *,
        parent_cycle_id: candidate_for(
            cycle,
            data,
            score=(
                80.0
                if cycle.underlying_symbol == "NIFTY"
                else 60.0
            ),
        )
    )
    return parent_input, nifty, sensex, runtime_readers


def test_authoritative_parent_persists_before_return(tmp_path):
    parent_input, nifty, sensex, runtime_readers = (
        runtime_inputs()
    )
    journal = PaperOrchestrationJournal(
        tmp_path / "parent.json"
    )
    adapter = TwoMarketParentCycleJournalAdapter(
        journal=journal,
        clock=lambda: NOW,
    )

    decision = run_authoritative_two_market_parent_cycle(
        parent_input,
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=runtime_readers,
        parent_journal_adapter=adapter,
    )

    assert journal.count() == 1

    raw = journal.get_raw(
        f"two-market-parent:{parent_input.parent_cycle_id}"
    )
    assert raw is not None
    assert raw["cycle_result"]["metadata"][
        "decision_result_id"
    ] == decision.decision_result_id
    assert raw["cycle_result"]["metadata"][
        "broker_order_submission"
    ] is False


def test_authoritative_duplicate_parent_is_no_change(tmp_path):
    parent_input, nifty, sensex, runtime_readers = (
        runtime_inputs()
    )
    journal = PaperOrchestrationJournal(
        tmp_path / "parent.json"
    )
    adapter = TwoMarketParentCycleJournalAdapter(
        journal=journal,
        clock=lambda: NOW,
    )

    first = run_authoritative_two_market_parent_cycle(
        parent_input,
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=runtime_readers,
        parent_journal_adapter=adapter,
    )
    second = run_authoritative_two_market_parent_cycle(
        parent_input,
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=runtime_readers,
        parent_journal_adapter=adapter,
    )

    assert first == second
    assert journal.count() == 1


def test_wrong_parent_journal_dependency_fails_closed():
    parent_input, nifty, sensex, runtime_readers = (
        runtime_inputs()
    )

    with pytest.raises(
        TypeError,
        match="parent_journal_adapter",
    ):
        run_authoritative_two_market_parent_cycle(
            parent_input,
            nifty_cycle=nifty,
            sensex_cycle=sensex,
            readers=runtime_readers,
            parent_journal_adapter=object(),
        )


def test_certified_parent_journal_uses_separate_path(tmp_path):
    paths = build_certified_persistence_paths(tmp_path)

    adapter = build_certified_parent_journal_adapter(
        clock=lambda: NOW,
        paths=paths,
    )

    assert adapter.journal.file_path == (
        tmp_path
        / "two_market_parent_decision_journal.json"
    )
    assert adapter.journal.file_path not in {
        paths.opportunity_journal_path,
        paths.monitoring_journal_path,
    }

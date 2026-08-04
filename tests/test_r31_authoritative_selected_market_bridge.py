from datetime import datetime, timezone

from services.paper_orchestration.authoritative_two_market_entry_point import (
    run_authoritative_two_market_selected_p6_cycle,
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
    30,
    tzinfo=timezone.utc,
)


class RetainedBundleMapping(dict):
    def __init__(self):
        super().__init__()
        self.lookups = []

    def get(self, key, default=None):
        self.lookups.append(key)
        return super().get(key, default)


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


def test_authoritative_selected_p6_persists_parent_before_bridge(
    tmp_path,
):
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
    bundles = RetainedBundleMapping()

    result = run_authoritative_two_market_selected_p6_cycle(
        parent_input,
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=runtime_readers,
        bridge_result_id="r31-bridge",
        evaluated_at=parent_input.completed_at,
        maximum_candidate_age_seconds=180.0,
        certified_p6_input_bundles=bundles,
        parent_journal_adapter=adapter,
    )

    assert journal.count() == 1
    assert result.status == "BLOCKED"
    assert result.blockers == (
        "CERTIFIED_P6_EVIDENCE_MISSING",
    )

    raw = journal.get_raw(
        f"two-market-parent:{parent_input.parent_cycle_id}"
    )
    assert raw is not None
    assert raw["cycle_result"]["metadata"][
        "decision_result_id"
    ] == parent_input.decision_result_id


def test_only_selected_market_bundle_is_looked_up():
    parent_input, nifty, sensex, runtime_readers = (
        runtime_inputs()
    )
    bundles = RetainedBundleMapping()

    result = run_authoritative_two_market_selected_p6_cycle(
        parent_input,
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=runtime_readers,
        bridge_result_id="r31-selected-only",
        evaluated_at=parent_input.completed_at,
        maximum_candidate_age_seconds=180.0,
        certified_p6_input_bundles=bundles,
    )

    assert result.bridge.selected_market == (
        "NIFTY",
        "NSE",
    )
    assert bundles.lookups == [
        ("NIFTY", "NSE"),
    ]


def test_losing_market_never_reaches_selected_planning():
    parent_input, nifty, sensex, runtime_readers = (
        runtime_inputs()
    )
    bundles = RetainedBundleMapping()

    result = run_authoritative_two_market_selected_p6_cycle(
        parent_input,
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=runtime_readers,
        bridge_result_id="r31-loser-blocked",
        evaluated_at=parent_input.completed_at,
        maximum_candidate_age_seconds=180.0,
        certified_p6_input_bundles=bundles,
    )

    assert result.bridge.selected_market == (
        "NIFTY",
        "NSE",
    )
    assert result.bridge.losing_market == (
        "SENSEX",
        "BSE",
    )
    assert ("SENSEX", "BSE") not in bundles.lookups

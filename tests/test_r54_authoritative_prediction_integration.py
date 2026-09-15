from dataclasses import replace

import pytest

from services.analysis.pre_entry_action_resolver import (
    resolve_pre_entry_market_action,
)
from services.paper_orchestration.authoritative_two_market_entry_point import (
    run_authoritative_two_market_parent_cycle,
)
from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
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


def _runtime():
    nifty, sensex = cycles()
    nifty = replace(
        nifty,
        metadata={
            **dict(nifty.metadata),
            "spot_price": 25000.0,
        },
    )
    sensex = replace(
        sensex,
        metadata={
            **dict(sensex.metadata),
            "spot_price": 80000.0,
        },
    )

    pre_entry_actions = {}

    def candidate_reader(
        cycle,
        data,
        analysis,
        captured,
        shared_context,
        *,
        parent_cycle_id,
    ):
        candidate = candidate_for(
            cycle,
            data,
            score=(
                80.0
                if cycle.underlying_symbol == "NIFTY"
                else 60.0
            ),
        )

        pre_entry_actions[cycle.observation_id] = (
            resolve_pre_entry_market_action(
                candidate=candidate,
                cycle_id=parent_cycle_id,
                observation_id=cycle.observation_id,
                evaluated_at=cycle.received_at,
            )
        )

        return candidate

    runtime_readers = readers(candidate_reader)

    return (
        nifty,
        sensex,
        runtime_readers,
        pre_entry_actions,
    )


def test_authoritative_parent_persists_exact_two_predictions(
    tmp_path,
):
    nifty, sensex, runtime_readers, pre_entry_actions = _runtime()
    parent_input = parent(nifty, sensex)
    ledger = PredictionLedger(
        tmp_path / "prediction-ledger.json"
    )

    decision = run_authoritative_two_market_parent_cycle(
        parent_input,
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=runtime_readers,
        pre_entry_actions=pre_entry_actions,
        prediction_ledger=ledger,
    )

    records = ledger.records_for_parent(
        parent_input.parent_cycle_id
    )

    assert decision.selected_market == (
        "NIFTY",
        "NSE",
    )
    assert ledger.count() == 2
    assert tuple(
        item["underlying_symbol"]
        for item in records
    ) == ("NIFTY", "SENSEX")
    assert tuple(
        item["predicted_action"]
        for item in records
    ) == ("CALL", "CALL")


def test_parent_journal_and_prediction_ledger_are_both_written(
    tmp_path,
):
    nifty, sensex, runtime_readers, pre_entry_actions = _runtime()
    parent_input = parent(nifty, sensex)
    parent_journal = PaperOrchestrationJournal(
        tmp_path / "parent-journal.json"
    )
    parent_adapter = TwoMarketParentCycleJournalAdapter(
        journal=parent_journal,
        clock=lambda: parent_input.completed_at,
    )
    prediction_ledger = PredictionLedger(
        tmp_path / "prediction-ledger.json"
    )

    run_authoritative_two_market_parent_cycle(
        parent_input,
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=runtime_readers,
        parent_journal_adapter=parent_adapter,
        pre_entry_actions=pre_entry_actions,
        prediction_ledger=prediction_ledger,
    )

    assert parent_journal.count() == 1
    assert prediction_ledger.count() == 2


def test_restart_duplicate_is_no_change(tmp_path):
    nifty, sensex, runtime_readers, pre_entry_actions = _runtime()
    parent_input = parent(nifty, sensex)
    path = tmp_path / "prediction-ledger.json"

    for _ in range(2):
        run_authoritative_two_market_parent_cycle(
            parent_input,
            nifty_cycle=nifty,
            sensex_cycle=sensex,
            readers=runtime_readers,
            pre_entry_actions=pre_entry_actions,
            prediction_ledger=PredictionLedger(path),
        )

    assert PredictionLedger(path).count() == 2


def test_wrong_prediction_ledger_exact_type_is_rejected():
    nifty, sensex, runtime_readers, pre_entry_actions = _runtime()

    with pytest.raises(
        TypeError,
        match="prediction_ledger",
    ):
        run_authoritative_two_market_parent_cycle(
            parent(nifty, sensex),
            nifty_cycle=nifty,
            sensex_cycle=sensex,
            readers=runtime_readers,
            prediction_ledger=object(),
        )

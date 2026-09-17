from dataclasses import replace

import pytest

from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_orchestration.prediction_record_projector import (
    project_parent_decision_predictions,
)
from services.analysis.pre_entry_action_resolver import (
    resolve_pre_entry_market_action,
)
from services.paper_orchestration.two_market_parent_cycle_coordinator import (
    run_two_market_parent_cycle,
)
from test_two_market_parent_cycle_coordinator import (
    candidate_for,
    parent,
)


def records():
    decision = run_two_market_parent_cycle(
        parent(),
        child_evaluator=(
            lambda symbol, exchange, observation_id: candidate_for(
                symbol,
                observation_id,
                score=(
                    80.0
                    if symbol == "NIFTY"
                    else 60.0
                ),
            )
        ),
    )
    pre_entry_actions = {
        entry.child.observation_id: resolve_pre_entry_market_action(
            candidate=entry.child.candidate,
            cycle_id=decision.parent_cycle_id,
            observation_id=entry.child.observation_id,
            evaluated_at=decision.completed_at,
        )
        for entry in decision.entries
        if entry.child.terminal_status == "COMPLETED"
    }
    return project_parent_decision_predictions(
        decision,
        start_underlying_prices={("NIFTY", "NSE"): 25000.0, ("SENSEX", "BSE"): 80000.0},
        pre_entry_actions=pre_entry_actions,
    )


def test_pair_is_atomic_durable_and_restart_readable(
    tmp_path,
):
    path = tmp_path / "prediction-ledger.json"
    pair = records()

    PredictionLedger(path).save_pair(pair)

    restarted = PredictionLedger(path)

    assert restarted.count() == 2
    restored = restarted.records_for_parent(
        pair[0].parent_cycle_id
    )
    assert tuple(
        item["underlying_symbol"]
        for item in restored
    ) == (
        "NIFTY",
        "SENSEX",
    )


def test_duplicate_pair_is_no_change(tmp_path):
    ledger = PredictionLedger(
        tmp_path / "prediction-ledger.json"
    )
    pair = records()

    ledger.save_pair(pair)
    ledger.save_pair(pair)

    assert ledger.count() == 2
    assert ledger.classify(
        prediction_id=pair[0].prediction_id,
        semantic_hash=pair[0].semantic_hash,
    ) == "DUPLICATE_SAME_PAYLOAD"


def test_conflict_rejects_pair_without_partial_write(
    tmp_path,
):
    ledger = PredictionLedger(
        tmp_path / "prediction-ledger.json"
    )
    pair = records()
    ledger.save_pair(pair)

    changed = (
        replace(
            pair[0],
            warnings=("CHANGED",),
        ),
        pair[1],
    )

    with pytest.raises(
        ValueError,
        match="IDEMPOTENCY_PAYLOAD_CONFLICT",
    ):
        ledger.save_pair(changed)

    assert ledger.count() == 2
    assert (
        ledger.get_raw(
            pair[0].prediction_id
        )["semantic_hash"]
        == pair[0].semantic_hash
    )


def test_corrupt_document_fails_closed(tmp_path):
    path = tmp_path / "prediction-ledger.json"
    path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="invalid JSON",
    ):
        PredictionLedger(path).count()


def test_all_records_is_restart_ordered(tmp_path):
    path = tmp_path / "prediction-ledger.json"
    pair = records()
    PredictionLedger(path).save_pair(pair)
    restored = PredictionLedger(path).all_records()
    assert tuple(item["underlying_symbol"] for item in restored) == ("NIFTY", "SENSEX")
    assert tuple(item["start_underlying_price"] for item in restored) == (25000.0, 80000.0)

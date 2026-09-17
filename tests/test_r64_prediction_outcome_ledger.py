from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from services.paper_orchestration.prediction_outcome_ledger import (
    PredictionOutcomeLedger,
)
from test_r61_prediction_outcome_record_v1 import (
    directional,
)


def test_outcome_is_durable_and_restart_readable(tmp_path):
    path = tmp_path / "prediction-outcome-ledger.json"
    record = directional()

    PredictionOutcomeLedger(path).save(record)

    restarted = PredictionOutcomeLedger(path)

    assert restarted.count() == 1
    restored = restarted.records_for_prediction(
        record.prediction_id
    )
    assert len(restored) == 1
    assert restored[0]["outcome"] == "CORRECT"


def test_duplicate_same_payload_is_no_change(tmp_path):
    ledger = PredictionOutcomeLedger(
        tmp_path / "prediction-outcome-ledger.json"
    )
    record = directional()

    ledger.save(record)
    ledger.save(record)

    assert ledger.count() == 1
    assert ledger.classify(
        outcome_id=record.outcome_id,
        semantic_hash=record.semantic_hash,
    ) == "DUPLICATE_SAME_PAYLOAD"


def test_changed_payload_conflicts(tmp_path):
    ledger = PredictionOutcomeLedger(
        tmp_path / "prediction-outcome-ledger.json"
    )
    record = directional()
    ledger.save(record)

    changed = replace(
        record,
        warnings=("CHANGED",),
    )

    with pytest.raises(
        ValueError,
        match="IDEMPOTENCY_PAYLOAD_CONFLICT",
    ):
        ledger.save(changed)

    assert ledger.count() == 1


def test_parent_lookup_is_ordered_nifty_then_sensex(tmp_path):
    ledger = PredictionOutcomeLedger(
        tmp_path / "prediction-outcome-ledger.json"
    )
    nifty = directional()
    sensex = replace(
        directional(),
        outcome_id="outcome:prediction-2",
        prediction_id="prediction-2",
        underlying_symbol="SENSEX",
        exchange="BSE",
    )

    ledger.save(sensex)
    ledger.save(nifty)

    restored = ledger.records_for_parent(
        nifty.parent_cycle_id
    )

    assert tuple(
        item["underlying_symbol"]
        for item in restored
    ) == ("NIFTY", "SENSEX")


def test_corrupt_document_fails_closed(tmp_path):
    path = tmp_path / "prediction-outcome-ledger.json"
    path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="invalid JSON",
    ):
        PredictionOutcomeLedger(path).count()

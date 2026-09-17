from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_prediction_lifecycle_context_store import Task9PredictionLifecycleContextStore
from services.certification.task9_prediction_paper_trade_binding_store import (
    Task9PredictionPaperTradeBindingStore,
    Task9PredictionPaperTradeBindingV1,
)
from services.certification.task9_prediction_lifecycle_timing import resolve_prediction_lifecycle_window
from services.contracts.prediction_lifecycle_timing_v1 import POLICY_ID
from services.market_session.policies import MarketSessionPolicy
from tests.test_task916_prediction_lifecycle_timing_policy import prediction


def context():
    record = prediction(observed_at=datetime(2026, 8, 10, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata")))
    return resolve_prediction_lifecycle_window(prediction_record=record, session_policy=MarketSessionPolicy())


def test_store_recovers_exact_window_and_is_idempotent(tmp_path):
    path = tmp_path / "contexts.json"; value = context()
    store = Task9PredictionLifecycleContextStore(path)
    assert store.save(value) == "SAVED"
    assert store.save(value) == "DUPLICATE_SAME_PAYLOAD"
    recovered = Task9PredictionLifecycleContextStore(path).recover(value.prediction_id)
    assert recovered == value
    assert recovered.policy_id == POLICY_ID


def test_no_trade_context_recovers_without_creating_a_paper_binding(tmp_path):
    record = prediction("NO_TRADE", datetime(2026, 8, 10, 15, 34, tzinfo=ZoneInfo("Asia/Kolkata")))
    value = resolve_prediction_lifecycle_window(prediction_record=record, session_policy=MarketSessionPolicy())
    contexts_path = tmp_path / "contexts.json"; bindings_path = tmp_path / "bindings.json"
    Task9PredictionLifecycleContextStore(contexts_path).save(value)
    assert Task9PredictionLifecycleContextStore(contexts_path).recover(value.prediction_id) == value
    assert not bindings_path.exists()


def test_store_rejects_conflict_and_corruption(tmp_path):
    path = tmp_path / "contexts.json"; value = context(); store = Task9PredictionLifecycleContextStore(path)
    store.save(value)
    from dataclasses import replace
    with pytest.raises(ValueError, match="conflicting"):
        store.save(replace(value, provenance="different"))
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid"):
        store.recover(value.prediction_id)


def test_restart_chain_trade_binding_to_exact_lifecycle_context(tmp_path):
    value = context()
    contexts_path = tmp_path / "contexts.json"; bindings_path = tmp_path / "bindings.json"
    Task9PredictionLifecycleContextStore(contexts_path).save(value)
    Task9PredictionPaperTradeBindingStore(bindings_path).save(
        Task9PredictionPaperTradeBindingV1(
            official_run_id="run", prediction_id=value.prediction_id,
            market="NIFTY", paper_trade_id="paper-trade", paper_position_id="position",
            option_symbol="NIFTY26AUG25000CE", entered_at=value.window_starts_at,
        )
    )
    binding = Task9PredictionPaperTradeBindingStore(bindings_path).by_trade("paper-trade")
    recovered = Task9PredictionLifecycleContextStore(contexts_path).recover(binding.prediction_id)
    assert (recovered.window_starts_at, recovered.entry_window_ends_at, recovered.validity_window_ends_at, recovered.policy_id) == (value.window_starts_at, value.entry_window_ends_at, value.validity_window_ends_at, POLICY_ID)

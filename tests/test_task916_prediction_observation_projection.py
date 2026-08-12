from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_prediction_observation_projection import project_task9_prediction_observation
from services.certification.task9_prediction_observation_recorder import Task9PredictionObservationRecorder
from services.certification.task9_prediction_observation_window_store import Task9PredictionObservationWindowStore
from services.certification.task9_prediction_lifecycle_timing import resolve_prediction_lifecycle_window
from services.certification.task9_prediction_paper_trade_binding_store import Task9PredictionPaperTradeBindingV1
from services.contracts.task9_prediction_paper_market_identity_v1 import build_task9_prediction_paper_market_identity
from services.market_session.policies import MarketSessionPolicy
from tests.p7_fixture_helpers import make_observation, make_open_position
from tests.test_task916_prediction_lifecycle_timing_policy import prediction

NOW = datetime(2026, 8, 10, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

def inputs():
    record = prediction("CALL", NOW); context = resolve_prediction_lifecycle_window(prediction_record=record, session_policy=MarketSessionPolicy())
    binding = Task9PredictionPaperTradeBindingV1("run", record.prediction_id, "NIFTY", "trade", "position", "NIFTY26AUG25000CE", NOW)
    bridge = build_task9_prediction_paper_market_identity(prediction=record, binding=binding)
    observation = make_observation(observed_at=NOW, received_at=NOW, exchange="NFO")
    return record, context, bridge, observation

def test_fresh_ordinary_and_unavailable_observations_use_documented_events(tmp_path):
    record, context, bridge, observation = inputs()
    fresh = project_task9_prediction_observation(prediction=record, bridge=bridge, lifecycle_context=context, paper_observation=observation, sequence_number=1)
    gap = project_task9_prediction_observation(prediction=record, bridge=bridge, lifecycle_context=context, paper_observation=replace(observation, observation_id="obs-2", data_quality_status="STALE"), sequence_number=2)
    assert (fresh.event_type, fresh.data_available, fresh.exchange) == ("NONE", True, "NSE")
    assert (gap.event_type, gap.data_available, gap.underlying_price, gap.option_premium) == ("DATA_GAP", False, None, None)
    store = Task9PredictionObservationWindowStore(tmp_path / "observations.json")
    store.initialize(prediction=record, entry_window_ends_at=context.entry_window_ends_at, validity_window_ends_at=context.validity_window_ends_at)
    recorder = Task9PredictionObservationRecorder(store); recorder.record(fresh); recorder.record(gap)
    assert Task9PredictionObservationWindowStore(store.file_path).recover(record.prediction_id).observation_count == 2

def test_persisted_entry_fill_maps_to_entry_and_nonfresh_fill_fails_closed():
    record, context, bridge, observation = inputs()
    fill = replace(make_open_position().entry_fill, observation_id=observation.observation_id, filled_at=NOW)
    entry = project_task9_prediction_observation(prediction=record, bridge=bridge, lifecycle_context=context, paper_observation=observation, lifecycle_fill=fill, sequence_number=1)
    assert (entry.event_type, entry.within_entry_window, entry.source_observation_id) == ("ENTRY", True, "obs-1")
    with pytest.raises(ValueError, match="fresh"):
        project_task9_prediction_observation(prediction=record, bridge=bridge, lifecycle_context=context, paper_observation=replace(observation, data_quality_status="PARTIAL"), lifecycle_fill=fill, sequence_number=1)

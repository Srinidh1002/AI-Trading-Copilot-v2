from datetime import timedelta
import pytest

from services.certification.task9_prediction_observation_window_store import Task9PredictionObservationWindowStore
from tests.test_r76_prediction_observation_window_tracker import observation
from test_r51_prediction_record_v1 import record

def test_store_recovers_ordered_window_and_is_idempotent(tmp_path):
    prediction = record(); store = Task9PredictionObservationWindowStore(tmp_path / "windows.json")
    store.initialize(prediction=prediction, entry_window_ends_at=prediction.completed_at + timedelta(minutes=5), validity_window_ends_at=prediction.completed_at + timedelta(minutes=15))
    first = observation(prediction=prediction, sequence_number=1); second = observation(prediction=prediction, sequence_number=2, seconds=60)
    assert store.append(first) == "SAVED"; assert store.append(first) == "DUPLICATE_SAME_PAYLOAD"; assert store.append(second) == "SAVED"
    recovered = Task9PredictionObservationWindowStore(tmp_path / "windows.json").recover(prediction.prediction_id)
    assert tuple(item.observation_id for item in recovered.observations) == (first.observation_id, second.observation_id)

def test_store_rejects_out_of_order_and_conflicting_observation(tmp_path):
    prediction = record(); store = Task9PredictionObservationWindowStore(tmp_path / "windows.json")
    store.initialize(prediction=prediction, entry_window_ends_at=prediction.completed_at + timedelta(minutes=5), validity_window_ends_at=prediction.completed_at + timedelta(minutes=15))
    with pytest.raises(ValueError): store.append(observation(prediction=prediction, sequence_number=2))

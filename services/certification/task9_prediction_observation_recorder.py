"""Task 9 durable prediction-observation recorder."""
from __future__ import annotations
from services.certification.task9_prediction_observation_window_store import Task9PredictionObservationWindowStore
from services.contracts.prediction_observation_v1 import PredictionObservationV1

class Task9PredictionObservationRecorder:
    def __init__(self, store: Task9PredictionObservationWindowStore):
        if type(store) is not Task9PredictionObservationWindowStore: raise TypeError("store")
        self.store = store
    def record_projected(self, *, prediction_id: str, source_observation_id: str | None, event_type: str, factory) -> PredictionObservationV1:
        return self.store.append_projected(prediction_id=prediction_id, source_observation_id=source_observation_id, event_type=event_type, factory=factory)
    def record(self, observation: PredictionObservationV1) -> PredictionObservationV1:
        """Compatibility seam for an already-sequenced legacy caller."""
        self.store.append(observation)
        return observation

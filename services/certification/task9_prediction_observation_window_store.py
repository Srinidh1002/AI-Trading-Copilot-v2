"""Durable, append-only Task 9 prediction observation evidence."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from services.contracts.prediction_observation_v1 import PredictionObservationV1
from services.contracts.prediction_record_v1 import PredictionRecordV1, prediction_record_from_dict
from services.prediction_outcomes.prediction_observation_window_tracker import build_prediction_observation_window


def _dt(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("timestamp")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp")
    return result


def _observation(value: object) -> PredictionObservationV1:
    if type(value) is not dict:
        raise ValueError("observation")
    payload = dict(value)
    payload["observed_at"] = _dt(payload.get("observed_at"))
    return PredictionObservationV1(**payload)


class Task9PredictionObservationWindowStore:
    """JSON persistence of source observations, never of a derived window."""
    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)

    def _read(self) -> dict[str, object]:
        if not self.file_path.exists():
            return {"version": 1, "windows": {}}
        value = json.loads(self.file_path.read_text(encoding="utf-8"))
        if type(value) is not dict or set(value) != {"version", "windows"} or value["version"] != 1 or type(value["windows"]) is not dict:
            raise ValueError("invalid Task 9 observation store")
        return value

    def _write(self, value: dict[str, object]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.file_path.with_suffix(self.file_path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False), encoding="utf-8")
            os.replace(temporary, self.file_path)
        finally:
            temporary.unlink(missing_ok=True)

    def initialize(self, *, prediction: PredictionRecordV1, entry_window_ends_at: datetime, validity_window_ends_at: datetime) -> str:
        if type(prediction) is not PredictionRecordV1:
            raise TypeError("prediction")
        document = self._read(); windows = document["windows"]
        record = {"prediction": prediction.to_dict(), "entry_window_ends_at": entry_window_ends_at.isoformat(), "validity_window_ends_at": validity_window_ends_at.isoformat(), "observations": []}
        current = windows.get(prediction.prediction_id)
        if current is not None:
            if {
                key: current[key]
                for key in record
                if key != "observations"
            } != {
                key: record[key]
                for key in record
                if key != "observations"
            }:
                raise ValueError("conflicting prediction window initialization")
            return "DUPLICATE_SAME_PAYLOAD"
        windows[prediction.prediction_id] = record; self._write(document)
        return "SAVED"


    def append(self, observation: PredictionObservationV1) -> str:
        if type(observation) is not PredictionObservationV1:
            raise TypeError("observation")
        document = self._read(); record = document["windows"].get(observation.prediction_id)
        if record is None: raise KeyError("prediction window not initialized")
        prediction = prediction_record_from_dict(record["prediction"])
        if (observation.parent_cycle_id, observation.underlying_symbol, observation.exchange) != (prediction.parent_cycle_id, prediction.underlying_symbol, prediction.exchange):
            raise ValueError("observation identity mismatch")
        observations = [_observation(item) for item in record["observations"]]
        same = next((item for item in observations if item.sequence_number == observation.sequence_number or item.observation_id == observation.observation_id), None)
        if same is not None:
            if same != observation: raise ValueError("conflicting duplicate observation")
            return "DUPLICATE_SAME_PAYLOAD"
        if observation.sequence_number != len(observations) + 1: raise ValueError("observation sequence")
        if observations and observation.observed_at < observations[-1].observed_at: raise ValueError("observation ordering")
        record["observations"].append(observation.to_dict()); self._write(document)
        return "SAVED"

    def append_projected(self, *, prediction_id: str, source_observation_id: str | None, event_type: str, factory) -> PredictionObservationV1:
        """Allocate a contiguous sequence and persist one projection in one transaction."""
        if type(prediction_id) is not str or not prediction_id.strip() or type(event_type) is not str or not event_type.strip() or not callable(factory):
            raise ValueError("projection identity")
        document = self._read(); record = document["windows"].get(prediction_id)
        if record is None: raise KeyError("prediction window not initialized")
        observations = [_observation(item) for item in record["observations"]]
        matches = [item for item in observations if item.source_observation_id == source_observation_id and item.event_type == event_type.upper()]
        if matches:
            projected = factory(matches[0].sequence_number)
            if projected != matches[0]: raise ValueError("conflicting duplicate source observation")
            return matches[0]
        projected = factory(len(observations) + 1)
        if type(projected) is not PredictionObservationV1 or projected.prediction_id != prediction_id or projected.sequence_number != len(observations) + 1 or projected.source_observation_id != source_observation_id or projected.event_type != event_type.upper():
            raise ValueError("projected observation mismatch")
        prediction = prediction_record_from_dict(record["prediction"])
        if (projected.parent_cycle_id, projected.underlying_symbol, projected.exchange) != (prediction.parent_cycle_id, prediction.underlying_symbol, prediction.exchange): raise ValueError("observation identity mismatch")
        if observations and projected.observed_at < observations[-1].observed_at: raise ValueError("observation ordering")
        record["observations"].append(projected.to_dict()); self._write(document)
        return projected

    def recover(self, prediction_id: str):
        record = self._read()["windows"].get(prediction_id)
        if record is None: return None
        prediction = prediction_record_from_dict(record["prediction"])
        return build_prediction_observation_window(prediction=prediction, observations=tuple(_observation(item) for item in record["observations"]), entry_window_ends_at=_dt(record["entry_window_ends_at"]), validity_window_ends_at=_dt(record["validity_window_ends_at"]))

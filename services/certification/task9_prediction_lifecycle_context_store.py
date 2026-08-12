"""Atomic durable storage for immutable Task 9 prediction lifecycle windows."""
from __future__ import annotations

import json
import os
from pathlib import Path

from services.contracts.prediction_lifecycle_timing_v1 import PredictionLifecycleWindowV1, prediction_lifecycle_window_from_dict


class Task9PredictionLifecycleContextStore:
    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)

    def _read(self) -> dict[str, object]:
        if not self.file_path.exists(): return {"version": 1, "contexts": {}}
        try: document = json.loads(self.file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc: raise ValueError("invalid lifecycle context JSON") from exc
        if type(document) is not dict or set(document) != {"version", "contexts"} or document["version"] != 1 or type(document["contexts"]) is not dict: raise ValueError("invalid lifecycle context store")
        for key, raw in document["contexts"].items():
            if key != raw.get("prediction_id"): raise ValueError("lifecycle context key mismatch")
            prediction_lifecycle_window_from_dict(raw)
        return document

    def _write(self, document: dict[str, object]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True); temporary = self.file_path.with_name(self.file_path.name + ".tmp")
        try:
            temporary.write_text(json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False), encoding="utf-8")
            os.replace(temporary, self.file_path)
        finally: temporary.unlink(missing_ok=True)

    def save(self, context: PredictionLifecycleWindowV1) -> str:
        if type(context) is not PredictionLifecycleWindowV1: raise TypeError("context")
        document = self._read(); raw = context.to_dict(); existing = document["contexts"].get(context.prediction_id)
        if existing is not None:
            if existing != raw: raise ValueError("conflicting lifecycle context")
            return "DUPLICATE_SAME_PAYLOAD"
        document["contexts"][context.prediction_id] = raw; self._write(document); return "SAVED"

    def recover(self, prediction_id: str) -> PredictionLifecycleWindowV1 | None:
        if not isinstance(prediction_id, str) or not prediction_id.strip(): raise ValueError("prediction_id")
        raw = self._read()["contexts"].get(prediction_id)
        return None if raw is None else prediction_lifecycle_window_from_dict(raw)

"""Durable Task 9 lifecycle-outcome authority."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from services.contracts.prediction_lifecycle_outcome_record_v1 import (
    PredictionLifecycleOutcomeRecordV1,
)


def _aware(value: object, name: str) -> datetime:
    if type(value) is not str:
        raise ValueError(name)

    result = datetime.fromisoformat(value)

    if (
        result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise ValueError(name)

    return result


def _record(
    raw: object,
) -> PredictionLifecycleOutcomeRecordV1:
    if type(raw) is not dict:
        raise ValueError(
            "invalid Task 9 lifecycle outcome record"
        )

    value = dict(raw)

    value["evaluated_at"] = _aware(
        value.get("evaluated_at"),
        "evaluated_at",
    )

    for name in (
        "entry_at",
        "terminal_event_at",
    ):
        item = value.get(name)
        value[name] = (
            None
            if item is None
            else _aware(item, name)
        )

    for name in (
        "evidence_observation_ids",
        "blockers",
        "warnings",
    ):
        item = value.get(name)

        if type(item) is not list:
            raise ValueError(name)

        value[name] = tuple(item)

    return PredictionLifecycleOutcomeRecordV1(
        **value
    )


class Task9PredictionLifecycleOutcomeStore:
    """Atomic immutable lifecycle outcome persistence."""

    VERSION = 1

    def __init__(
        self,
        file_path: str | Path,
    ) -> None:
        self.file_path = Path(file_path)

    def _empty(self) -> dict[str, object]:
        return {
            "version": self.VERSION,
            "by_prediction": {},
            "by_outcome": {},
        }

    def _read(self) -> dict[str, object]:
        if not self.file_path.exists():
            return self._empty()

        try:
            value = json.loads(
                self.file_path.read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                "invalid Task 9 lifecycle outcome store"
            ) from exc

        if (
            type(value) is not dict
            or set(value)
            != {
                "version",
                "by_prediction",
                "by_outcome",
            }
            or value.get("version") != self.VERSION
            or type(value.get("by_prediction"))
            is not dict
            or type(value.get("by_outcome"))
            is not dict
        ):
            raise ValueError(
                "invalid Task 9 lifecycle outcome store"
            )

        return value

    def _write(
        self,
        document: dict[str, object],
    ) -> None:
        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = self.file_path.with_suffix(
            self.file_path.suffix + ".tmp"
        )

        try:
            temporary.write_text(
                json.dumps(
                    document,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
                encoding="utf-8",
            )
            os.replace(
                temporary,
                self.file_path,
            )
        finally:
            temporary.unlink(
                missing_ok=True
            )

    def save(
        self,
        record: PredictionLifecycleOutcomeRecordV1,
    ) -> str:
        if (
            type(record)
            is not PredictionLifecycleOutcomeRecordV1
        ):
            raise TypeError("record")

        document = self._read()
        raw = record.to_dict()

        by_prediction = document[
            "by_prediction"
        ]
        by_outcome = document[
            "by_outcome"
        ]

        prediction_existing = by_prediction.get(
            record.prediction_id
        )
        outcome_existing = by_outcome.get(
            record.outcome_id
        )

        for existing in (
            prediction_existing,
            outcome_existing,
        ):
            if existing is not None:
                if existing != raw:
                    raise ValueError(
                        "conflicting Task 9 lifecycle outcome"
                    )

        if (
            prediction_existing is not None
            or outcome_existing is not None
        ):
            if (
                prediction_existing != raw
                or outcome_existing != raw
            ):
                raise ValueError(
                    "incomplete Task 9 lifecycle outcome index"
                )

            return "DUPLICATE_SAME_PAYLOAD"

        by_prediction[
            record.prediction_id
        ] = raw

        by_outcome[
            record.outcome_id
        ] = raw

        self._write(document)

        return "SAVED"

    def by_prediction(
        self,
        prediction_id: str,
    ) -> PredictionLifecycleOutcomeRecordV1 | None:
        if (
            type(prediction_id) is not str
            or not prediction_id.strip()
        ):
            raise ValueError("prediction_id")

        raw = self._read()[
            "by_prediction"
        ].get(
            prediction_id.strip()
        )

        return (
            None
            if raw is None
            else _record(raw)
        )

    def by_outcome(
        self,
        outcome_id: str,
    ) -> PredictionLifecycleOutcomeRecordV1 | None:
        if (
            type(outcome_id) is not str
            or not outcome_id.strip()
        ):
            raise ValueError("outcome_id")

        raw = self._read()[
            "by_outcome"
        ].get(
            outcome_id.strip()
        )

        return (
            None
            if raw is None
            else _record(raw)
        )

    def recover(
        self,
        prediction_id: str,
    ) -> PredictionLifecycleOutcomeRecordV1 | None:
        return self.by_prediction(
            prediction_id
        )
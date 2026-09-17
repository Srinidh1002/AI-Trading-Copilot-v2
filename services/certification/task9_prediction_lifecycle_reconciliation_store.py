"""Durable Task 9 lifecycle-reconciliation authority."""
from __future__ import annotations

from services.certification.task9_atomic_file_replace import replace_task9_atomic_file

import json
import os
from datetime import datetime
from pathlib import Path

from services.contracts.prediction_lifecycle_reconciliation_result_v1 import (
    PredictionLifecycleReconciliationResultV1,
)


def _aware(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("reconciled_at")

    result = datetime.fromisoformat(value)

    if (
        result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise ValueError("reconciled_at")

    return result


def _record(
    raw: object,
) -> PredictionLifecycleReconciliationResultV1:
    if type(raw) is not dict:
        raise ValueError(
            "invalid Task 9 lifecycle reconciliation record"
        )

    value = dict(raw)

    value["reconciled_at"] = _aware(
        value.get("reconciled_at")
    )

    for name in (
        "blockers",
        "warnings",
    ):
        item = value.get(name)

        if type(item) is not list:
            raise ValueError(name)

        value[name] = tuple(item)

    return PredictionLifecycleReconciliationResultV1(
        **value
    )


class Task9PredictionLifecycleReconciliationStore:
    """Atomic immutable reconciliation persistence."""

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
            "by_reconciliation": {},
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
                "invalid Task 9 lifecycle reconciliation store"
            ) from exc

        if (
            type(value) is not dict
            or set(value)
            != {
                "version",
                "by_prediction",
                "by_reconciliation",
            }
            or value.get("version") != self.VERSION
            or type(value.get("by_prediction"))
            is not dict
            or type(value.get("by_reconciliation"))
            is not dict
        ):
            raise ValueError(
                "invalid Task 9 lifecycle reconciliation store"
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
            replace_task9_atomic_file(
                temporary,
                self.file_path,
            )
        finally:
            temporary.unlink(
                missing_ok=True
            )

    def save(
        self,
        result: PredictionLifecycleReconciliationResultV1,
    ) -> str:
        if (
            type(result)
            is not PredictionLifecycleReconciliationResultV1
        ):
            raise TypeError("result")

        document = self._read()
        raw = result.to_dict()

        by_prediction = document[
            "by_prediction"
        ]
        by_reconciliation = document[
            "by_reconciliation"
        ]

        prediction_existing = by_prediction.get(
            result.prediction_id
        )
        reconciliation_existing = (
            by_reconciliation.get(
                result.reconciliation_id
            )
        )

        for existing in (
            prediction_existing,
            reconciliation_existing,
        ):
            if existing is not None:
                if existing != raw:
                    raise ValueError(
                        "conflicting Task 9 lifecycle reconciliation"
                    )

        if (
            prediction_existing is not None
            or reconciliation_existing is not None
        ):
            if (
                prediction_existing != raw
                or reconciliation_existing != raw
            ):
                raise ValueError(
                    "incomplete Task 9 lifecycle reconciliation index"
                )

            return "DUPLICATE_SAME_PAYLOAD"

        by_prediction[
            result.prediction_id
        ] = raw

        by_reconciliation[
            result.reconciliation_id
        ] = raw

        self._write(document)

        return "SAVED"

    def by_prediction(
        self,
        prediction_id: str,
    ) -> PredictionLifecycleReconciliationResultV1 | None:
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

    def by_reconciliation(
        self,
        reconciliation_id: str,
    ) -> PredictionLifecycleReconciliationResultV1 | None:
        if (
            type(reconciliation_id) is not str
            or not reconciliation_id.strip()
        ):
            raise ValueError(
                "reconciliation_id"
            )

        raw = self._read()[
            "by_reconciliation"
        ].get(
            reconciliation_id.strip()
        )

        return (
            None
            if raw is None
            else _record(raw)
        )

    def recover(
        self,
        prediction_id: str,
    ) -> PredictionLifecycleReconciliationResultV1 | None:
        return self.by_prediction(
            prediction_id
        )
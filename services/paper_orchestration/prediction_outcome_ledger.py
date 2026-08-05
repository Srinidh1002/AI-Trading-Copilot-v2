"""Atomic immutable ledger for prediction outcome records."""
from __future__ import annotations

import json
import os
from pathlib import Path

from services.contracts.prediction_outcome_record_v1 import (
    PredictionOutcomeRecordV1,
)


class PredictionOutcomeLedger:
    """Durable append-only outcome ledger keyed by deterministic outcome ID."""

    SCHEMA_VERSION = 1

    def __init__(self, file_path=None):
        self.file_path = Path(
            file_path
            or (
                "data/paper_trading/certified_runtime/"
                "prediction_outcome_ledger.json"
            )
        )

    @classmethod
    def _empty_document(cls):
        return {
            "version": cls.SCHEMA_VERSION,
            "records": {},
        }

    @classmethod
    def _validate_document(cls, document):
        if type(document) is not dict:
            raise ValueError(
                "prediction outcome ledger must contain a JSON object"
            )
        if document.get("version") != cls.SCHEMA_VERSION:
            raise ValueError(
                "unsupported prediction outcome ledger version"
            )

        records = document.get("records")
        if type(records) is not dict:
            raise ValueError(
                "prediction outcome ledger records must be a dictionary"
            )

        normalized = {}
        for key, value in records.items():
            if type(key) is not str or not key.strip():
                raise ValueError(
                    "prediction outcome ledger key must be non-empty"
                )
            if type(value) is not dict:
                raise ValueError(
                    "prediction outcome ledger record must be a dictionary"
                )
            if value.get("outcome_id") != key:
                raise ValueError(
                    "prediction outcome ledger record key mismatch"
                )
            semantic_hash = value.get("semantic_hash")
            if (
                type(semantic_hash) is not str
                or len(semantic_hash) != 64
            ):
                raise ValueError(
                    "prediction outcome ledger semantic hash"
                )
            normalized[key] = dict(value)

        return {
            "version": cls.SCHEMA_VERSION,
            "records": normalized,
        }

    def _read_document(self):
        if not self.file_path.exists():
            return self._empty_document()

        try:
            with self.file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                document = json.load(file)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "invalid JSON in prediction outcome ledger"
            ) from exc

        return self._validate_document(document)

    def _write_document(self, document):
        validated = self._validate_document(document)
        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self.file_path.with_name(
            self.file_path.name + ".tmp"
        )
        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    validated,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                file.flush()
                os.fsync(file.fileno())

            os.replace(
                temporary_path,
                self.file_path,
            )
        except Exception:
            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except OSError:
                pass
            raise

    def get_raw(self, outcome_id):
        if type(outcome_id) is not str:
            raise TypeError(
                "outcome_id must be a string"
            )

        key = outcome_id.strip()
        if not key:
            raise ValueError(
                "outcome_id must be non-empty"
            )

        value = self._read_document()["records"].get(key)
        return None if value is None else dict(value)

    def classify(
        self,
        *,
        outcome_id: str,
        semantic_hash: str,
    ) -> str:
        raw = self.get_raw(outcome_id)
        if raw is None:
            return "NEW"
        if raw.get("semantic_hash") == semantic_hash:
            return "DUPLICATE_SAME_PAYLOAD"
        return "IDEMPOTENCY_PAYLOAD_CONFLICT"

    def save(
        self,
        record: PredictionOutcomeRecordV1,
    ) -> PredictionOutcomeRecordV1:
        if type(record) is not PredictionOutcomeRecordV1:
            raise TypeError(
                "record must be exact PredictionOutcomeRecordV1"
            )

        document = self._read_document()
        existing = document["records"].get(
            record.outcome_id
        )

        if existing is not None:
            if (
                existing.get("semantic_hash")
                == record.semantic_hash
            ):
                return record
            raise ValueError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT"
            )

        document["records"][record.outcome_id] = {
            **record.to_dict(),
            "semantic_hash": record.semantic_hash,
        }
        self._write_document(document)
        return record

    def has_outcome_for_prediction(self, prediction_id) -> bool:
        return bool(self.records_for_prediction(prediction_id))

    def records_for_prediction(
        self,
        prediction_id,
    ) -> tuple[dict, ...]:
        if (
            type(prediction_id) is not str
            or not prediction_id.strip()
        ):
            raise ValueError(
                "prediction_id must be non-empty"
            )

        records = tuple(
            dict(value)
            for value in self._read_document()[
                "records"
            ].values()
            if value.get("prediction_id")
            == prediction_id.strip()
        )

        return tuple(
            sorted(
                records,
                key=lambda item: (
                    item["evaluation_due_at"],
                    item["outcome_id"],
                ),
            )
        )

    def records_for_parent(
        self,
        parent_cycle_id,
    ) -> tuple[dict, ...]:
        if (
            type(parent_cycle_id) is not str
            or not parent_cycle_id.strip()
        ):
            raise ValueError(
                "parent_cycle_id must be non-empty"
            )

        records = tuple(
            dict(value)
            for value in self._read_document()[
                "records"
            ].values()
            if value.get("parent_cycle_id")
            == parent_cycle_id.strip()
        )

        return tuple(
            sorted(
                records,
                key=lambda item: (
                    0
                    if item["underlying_symbol"]
                    == "NIFTY"
                    else 1,
                    item["evaluation_due_at"],
                    item["outcome_id"],
                ),
            )
        )

    def count(self) -> int:
        return len(
            self._read_document()["records"]
        )

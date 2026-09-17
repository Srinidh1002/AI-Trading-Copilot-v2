"""Atomic immutable ledger for exact two-market prediction records."""
from __future__ import annotations

import json
import os
from pathlib import Path

from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.contracts.prediction_record_v1 import prediction_record_from_dict


class PredictionLedger:
    """Durable append-only ledger keyed by deterministic prediction identity."""

    SCHEMA_VERSION = 1

    def __init__(self, file_path=None):
        self.file_path = Path(
            file_path
            or (
                "data/paper_trading/certified_runtime/"
                "prediction_ledger.json"
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
                "prediction ledger must contain a JSON object"
            )
        if document.get("version") != cls.SCHEMA_VERSION:
            raise ValueError(
                "unsupported prediction ledger version"
            )

        records = document.get("records")
        if type(records) is not dict:
            raise ValueError(
                "prediction ledger records must be a dictionary"
            )

        normalized = {}
        for key, value in records.items():
            if type(key) is not str or not key.strip():
                raise ValueError(
                    "prediction ledger key must be non-empty"
                )
            if type(value) is not dict:
                raise ValueError(
                    "prediction ledger record must be a dictionary"
                )
            if value.get("prediction_id") != key:
                raise ValueError(
                    "prediction ledger record key mismatch"
                )
            semantic_hash = value.get("semantic_hash")
            if (
                type(semantic_hash) is not str
                or len(semantic_hash) != 64
            ):
                raise ValueError(
                    "prediction ledger semantic hash"
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
                "invalid JSON in prediction ledger"
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

    def get_raw(self, prediction_id):
        if type(prediction_id) is not str:
            raise TypeError(
                "prediction_id must be a string"
            )

        key = prediction_id.strip()
        if not key:
            raise ValueError(
                "prediction_id must be non-empty"
            )

        value = self._read_document()["records"].get(key)
        return None if value is None else dict(value)

    def recover(self, prediction_id: str) -> PredictionRecordV1 | None:
        """Recover the exact durable prediction record by its only lookup key."""
        raw = self.get_raw(prediction_id)
        if raw is None:
            return None
        return prediction_record_from_dict(raw)

    def classify(
        self,
        *,
        prediction_id: str,
        semantic_hash: str,
    ) -> str:
        raw = self.get_raw(prediction_id)
        if raw is None:
            return "NEW"
        if raw.get("semantic_hash") == semantic_hash:
            return "DUPLICATE_SAME_PAYLOAD"
        return "IDEMPOTENCY_PAYLOAD_CONFLICT"

    def save_pair(
        self,
        records: tuple[
            PredictionRecordV1,
            PredictionRecordV1,
        ],
    ) -> tuple[
        PredictionRecordV1,
        PredictionRecordV1,
    ]:
        if (
            not isinstance(records, tuple)
            or len(records) != 2
            or not all(
                type(item) is PredictionRecordV1
                for item in records
            )
        ):
            raise TypeError(
                "exact prediction record pair required"
            )

        if tuple(
            (
                item.underlying_symbol,
                item.exchange,
            )
            for item in records
        ) != (
            ("NIFTY", "NSE"),
            ("SENSEX", "BSE"),
        ):
            raise ValueError(
                "exact ordered NIFTY/SENSEX pair required"
            )

        if len(
            {
                item.parent_cycle_id
                for item in records
            }
        ) != 1:
            raise ValueError(
                "prediction pair parent mismatch"
            )
        if len(
            {
                item.decision_result_id
                for item in records
            }
        ) != 1:
            raise ValueError(
                "prediction pair decision mismatch"
            )
        if len(
            {
                item.prediction_id
                for item in records
            }
        ) != 2:
            raise ValueError(
                "prediction IDs must be distinct"
            )

        document = self._read_document()

        for record in records:
            existing = document["records"].get(
                record.prediction_id
            )
            if (
                existing is not None
                and existing.get("semantic_hash")
                != record.semantic_hash
            ):
                raise ValueError(
                    "IDEMPOTENCY_PAYLOAD_CONFLICT"
                )

        changed = False
        for record in records:
            if record.prediction_id in document["records"]:
                continue
            document["records"][record.prediction_id] = {
                **record.to_dict(),
                "semantic_hash": record.semantic_hash,
            }
            changed = True

        if changed:
            self._write_document(document)

        return records

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
                    item["prediction_id"],
                ),
            )
        )

    def all_records(self) -> tuple[dict, ...]:
        records = tuple(dict(value) for value in self._read_document()["records"].values())
        return tuple(sorted(records, key=lambda item: (item["completed_at"], 0 if item["underlying_symbol"] == "NIFTY" else 1, item["prediction_id"])))

    def count(self) -> int:
        return len(
            self._read_document()["records"]
        )

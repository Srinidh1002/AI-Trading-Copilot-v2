from __future__ import annotations

import json
import os
from pathlib import Path

from services.contracts.paper_orchestration_journal_record_v1 import (
    PaperOrchestrationJournalRecordV1,
)


class PaperOrchestrationJournal:
    """Atomic PAPER-only journal for completed deterministic cycles."""

    SCHEMA_VERSION = 1

    def __init__(self, file_path=None):
        if file_path is None:
            file_path = (
                "data/paper_trading/"
                "paper_orchestration_journal.json"
            )
        self.file_path = Path(file_path)

    @classmethod
    def _empty_document(cls):
        return {
            "version": cls.SCHEMA_VERSION,
            "records": {},
        }

    @classmethod
    def _validate_document(cls, document):
        if type(document) is not dict:
            raise ValueError("journal must contain a JSON object")
        if document.get("version") != cls.SCHEMA_VERSION:
            raise ValueError("unsupported journal version")
        records = document.get("records")
        if type(records) is not dict:
            raise ValueError("journal records must be a dictionary")

        normalized = {}
        for key, value in records.items():
            if type(key) is not str or not key.strip():
                raise ValueError("journal key must be non-empty")
            if type(value) is not dict:
                raise ValueError("journal record must be a dictionary")
            if value.get("cycle_idempotency_key") != key:
                raise ValueError("journal record key mismatch")
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
                f"invalid JSON in orchestration journal: {exc}"
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
            os.replace(temporary_path, self.file_path)
        except Exception:
            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except OSError:
                pass
            raise

    def get_raw(self, cycle_idempotency_key):
        if type(cycle_idempotency_key) is not str:
            raise TypeError(
                "cycle_idempotency_key must be a string"
            )
        key = cycle_idempotency_key.strip()
        if not key:
            raise ValueError(
                "cycle_idempotency_key must be non-empty"
            )
        value = self._read_document()["records"].get(key)
        return None if value is None else dict(value)

    def classify(
        self,
        *,
        cycle_idempotency_key: str,
        cycle_input_semantic_hash: str,
    ) -> str:
        raw = self.get_raw(cycle_idempotency_key)
        if raw is None:
            return "NEW"

        prior_hash = raw.get("cycle_input_semantic_hash")
        if prior_hash == cycle_input_semantic_hash:
            return "DUPLICATE_SAME_PAYLOAD"
        return "IDEMPOTENCY_PAYLOAD_CONFLICT"

    def save(
        self,
        record: PaperOrchestrationJournalRecordV1,
    ) -> PaperOrchestrationJournalRecordV1:
        if type(record) is not PaperOrchestrationJournalRecordV1:
            raise TypeError(
                "record must be an exact "
                "PaperOrchestrationJournalRecordV1"
            )

        document = self._read_document()
        key = record.cycle_idempotency_key
        existing = document["records"].get(key)
        if existing is not None:
            prior_hash = existing.get(
                "cycle_input_semantic_hash"
            )
            if prior_hash == record.cycle_input_semantic_hash:
                return record
            raise ValueError("IDEMPOTENCY_PAYLOAD_CONFLICT")

        document["records"][key] = {
            **record.to_dict(),
            "integrity_hash": record.integrity_hash,
        }
        self._write_document(document)
        return record

    def count(self) -> int:
        return len(self._read_document()["records"])

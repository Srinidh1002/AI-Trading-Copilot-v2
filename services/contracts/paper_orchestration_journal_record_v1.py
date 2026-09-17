from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class PaperOrchestrationJournalRecordV1:
    journal_record_id: str
    cycle_idempotency_key: str
    cycle_input_semantic_hash: str
    cycle_result: PaperOrchestrationCycleResultV1
    persisted_at: datetime
    schema_version: str = "paper_orchestration_journal_record.v1"
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != "paper_orchestration_journal_record.v1":
            raise ValueError("unsupported schema_version")
        for name in ("journal_record_id", "cycle_idempotency_key"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        digest = _text(
            self.cycle_input_semantic_hash,
            "cycle_input_semantic_hash",
        ).lower()
        if len(digest) != 64 or any(
            item not in "0123456789abcdef" for item in digest
        ):
            raise ValueError(
                "cycle_input_semantic_hash must be a SHA-256 digest"
            )
        object.__setattr__(
            self,
            "cycle_input_semantic_hash",
            digest,
        )

        if type(self.cycle_result) is not PaperOrchestrationCycleResultV1:
            raise TypeError(
                "cycle_result must be an exact "
                "PaperOrchestrationCycleResultV1"
            )
        if (
            self.cycle_result.cycle_idempotency_key
            != self.cycle_idempotency_key
        ):
            raise ValueError("cycle idempotency identity mismatch")
        if (
            self.cycle_result.cycle_input_semantic_hash
            != self.cycle_input_semantic_hash
        ):
            raise ValueError("cycle input hash mismatch")

        object.__setattr__(
            self,
            "persisted_at",
            _aware(self.persisted_at, "persisted_at"),
        )

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")

    @property
    def integrity_hash(self) -> str:
        return hashlib.sha256(
            self.to_json().encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "journal_record_id": self.journal_record_id,
            "cycle_idempotency_key": self.cycle_idempotency_key,
            "cycle_input_semantic_hash": (
                self.cycle_input_semantic_hash
            ),
            "cycle_result": self.cycle_result.to_dict(),
            "persisted_at": self.persisted_at.isoformat(),
            "schema_version": self.schema_version,
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

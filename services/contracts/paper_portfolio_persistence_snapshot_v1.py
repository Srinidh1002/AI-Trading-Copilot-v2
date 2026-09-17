"""Canonical JSON-only persistence envelope for typed P8 portfolio state."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from .paper_portfolio_snapshot_v1 import PaperPortfolioSnapshotV1


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _string_mapping(value: object, name: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    items: list[tuple[str, str]] = []
    for key, item in value.items():
        items.append((_text(key, f"{name} key"), _text(item, f"{name} value")))
    keys = [key for key, _ in items]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{name} contains duplicate keys")
    return tuple(sorted(items))


@dataclass(frozen=True, slots=True)
class PaperPortfolioPersistenceSnapshotV1:
    portfolio_id: str
    portfolio_snapshot: PaperPortfolioSnapshotV1
    admission_idempotency_records: Mapping[str, str]
    update_idempotency_records: Mapping[str, str]
    processed_portfolio_event_hashes: Mapping[str, str]
    processed_p7_transition_hashes: Mapping[str, str]
    processed_p7_fill_hashes: Mapping[str, str]
    created_at: datetime
    updated_at: datetime
    event_sequence: int
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "portfolio_id", _text(self.portfolio_id, "portfolio_id"))
        if type(self.portfolio_snapshot) is not PaperPortfolioSnapshotV1:
            raise TypeError("portfolio_snapshot must be exact PaperPortfolioSnapshotV1")
        if self.portfolio_snapshot.portfolio_id != self.portfolio_id:
            raise ValueError("portfolio identity mismatch")

        for name in (
            "admission_idempotency_records",
            "update_idempotency_records",
            "processed_portfolio_event_hashes",
            "processed_p7_transition_hashes",
            "processed_p7_fill_hashes",
        ):
            object.__setattr__(self, name, _string_mapping(getattr(self, name), name))

        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _aware(self.updated_at, "updated_at"))
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if type(self.event_sequence) is not int or isinstance(self.event_sequence, bool):
            raise TypeError("event_sequence must be an exact int")
        if self.event_sequence < 0:
            raise ValueError("event_sequence must be nonnegative")
        if self.event_sequence != self.portfolio_snapshot.event_sequence:
            raise ValueError("event_sequence mismatch")

        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only persistence snapshot required")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "portfolio_snapshot": self.portfolio_snapshot.to_dict(),
            "admission_idempotency_records": dict(self.admission_idempotency_records),
            "update_idempotency_records": dict(self.update_idempotency_records),
            "processed_portfolio_event_hashes": dict(self.processed_portfolio_event_hashes),
            "processed_p7_transition_hashes": dict(self.processed_p7_transition_hashes),
            "processed_p7_fill_hashes": dict(self.processed_p7_fill_hashes),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "event_sequence": self.event_sequence,
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def integrity_hash(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

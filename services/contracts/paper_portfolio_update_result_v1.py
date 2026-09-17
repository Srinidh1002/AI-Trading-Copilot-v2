"""Immutable PAPER-only result of P8 portfolio lifecycle updates."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from .paper_capital_reservation_v1 import PaperCapitalReservationV1
from .paper_portfolio_snapshot_v1 import PaperPortfolioSnapshotV1

_STATUSES = frozenset({"APPLIED", "NO_CHANGE", "BLOCKED"})


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _diagnostics(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be an exact tuple")
    result: list[str] = []
    for item in value:
        item = _text(item, name)
        if item not in result:
            result.append(item)
    return tuple(result)


def _freeze(value: object) -> Any:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("metadata must be JSON-safe")
        return value
    if isinstance(value, Mapping):
        return MappingProxyType(
            dict(sorted((_text(k, "metadata key"), _freeze(v)) for k, v in value.items()))
        )
    if type(value) in (tuple, list):
        return tuple(_freeze(item) for item in value)
    raise ValueError("metadata must be JSON-safe")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class PaperPortfolioUpdateResultV1:
    update_result_id: str
    update_request_id: str
    update_idempotency_key: str
    update_payload_hash: str
    portfolio_event_id: str
    portfolio_id: str
    status: str
    decision: str
    source_snapshot_id: str
    result_snapshot_id: str
    source_event_sequence: int
    result_event_sequence: int
    resulting_snapshot: PaperPortfolioSnapshotV1
    evaluated_at: datetime
    resulting_reservation: PaperCapitalReservationV1 | None = None
    applied_p7_transition_ids: tuple[str, ...] = ()
    applied_p7_fill_ids: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in (
            "update_result_id",
            "update_request_id",
            "update_idempotency_key",
            "update_payload_hash",
            "portfolio_event_id",
            "portfolio_id",
            "source_snapshot_id",
            "result_snapshot_id",
            "decision",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if self.status not in _STATUSES:
            raise ValueError("unsupported update status")
        for name in ("source_event_sequence", "result_event_sequence"):
            value = getattr(self, name)
            if type(value) is not int or isinstance(value, bool):
                raise TypeError(f"{name} must be an exact int")
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if type(self.resulting_snapshot) is not PaperPortfolioSnapshotV1:
            raise TypeError("resulting_snapshot must be exact PaperPortfolioSnapshotV1")
        if self.resulting_reservation is not None and type(
            self.resulting_reservation
        ) is not PaperCapitalReservationV1:
            raise TypeError("resulting_reservation has wrong type")
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))

        for name in ("applied_p7_transition_ids", "applied_p7_fill_ids"):
            value = getattr(self, name)
            if type(value) is not tuple:
                raise TypeError(f"{name} must be an exact tuple")
            normalized = tuple(_text(item, name) for item in value)
            if len(normalized) != len(set(normalized)):
                raise ValueError(f"{name} contains duplicates")
            object.__setattr__(self, name, normalized)

        for name in ("blockers", "decision_reasons", "warnings"):
            object.__setattr__(self, name, _diagnostics(getattr(self, name), name))

        if self.resulting_snapshot.portfolio_id != self.portfolio_id:
            raise ValueError("snapshot portfolio mismatch")
        if self.resulting_snapshot.portfolio_snapshot_id != self.result_snapshot_id:
            raise ValueError("result_snapshot_id mismatch")
        if self.resulting_snapshot.event_sequence != self.result_event_sequence:
            raise ValueError("result event sequence mismatch")

        if self.status == "APPLIED":
            if self.blockers:
                raise ValueError("APPLIED cannot contain blockers")
            if self.result_event_sequence != self.source_event_sequence + 1:
                raise ValueError("APPLIED must increment exactly once")
            if self.result_snapshot_id == self.source_snapshot_id:
                raise ValueError("APPLIED requires a new snapshot ID")
        elif self.status == "NO_CHANGE":
            if self.blockers:
                raise ValueError("NO_CHANGE cannot contain blockers")
            if self.result_event_sequence != self.source_event_sequence:
                raise ValueError("NO_CHANGE cannot increment sequence")
            if self.result_snapshot_id != self.source_snapshot_id:
                raise ValueError("NO_CHANGE must retain snapshot identity")
            if self.applied_p7_transition_ids or self.applied_p7_fill_ids:
                raise ValueError("NO_CHANGE cannot apply new evidence")
        else:
            if not self.blockers:
                raise ValueError("BLOCKED requires blockers")
            if self.result_event_sequence != self.source_event_sequence:
                raise ValueError("BLOCKED cannot increment sequence")
            if self.result_snapshot_id != self.source_snapshot_id:
                raise ValueError("BLOCKED must retain snapshot identity")

        object.__setattr__(self, "metadata", _freeze(self.metadata))
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only update result required")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        result["resulting_snapshot"] = self.resulting_snapshot.to_dict()
        result["resulting_reservation"] = (
            None if self.resulting_reservation is None else self.resulting_reservation.to_dict()
        )
        result["evaluated_at"] = self.evaluated_at.isoformat()
        for name in (
            "applied_p7_transition_ids",
            "applied_p7_fill_ids",
            "blockers",
            "decision_reasons",
            "warnings",
        ):
            result[name] = list(result[name])
        result["metadata"] = _plain(self.metadata)
        return result

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        result.pop("update_result_id")
        result.pop("evaluated_at")
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

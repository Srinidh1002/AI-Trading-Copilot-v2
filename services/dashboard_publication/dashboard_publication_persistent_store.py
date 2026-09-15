"""Atomic, typed, cross-process persistence for dashboard publications."""
from __future__ import annotations

import json
import os
from dataclasses import MISSING, fields, is_dataclass
from datetime import date, datetime
from pathlib import Path
from types import UnionType
from typing import Any, ClassVar, Mapping, get_args, get_origin, get_type_hints

from services.contracts.task9_live_paper_certification_progress_v1 import (
    Task9MarketProgressV1,
)

from .dashboard_publication_snapshot_v1 import DashboardPublicationSnapshotV1


_SCHEMA_VERSION = "dashboard_publication_persistent_store.v1"
_FILENAME = "dashboard-publication.json"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if type(value) is not dict:
        raise ValueError(f"{name} must be a JSON object")
    return value


def _datetime(value: object, name: str) -> datetime:
    if type(value) is not str:
        raise ValueError(name)
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(name) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(name)
    return result


def _date(value: object, name: str) -> date:
    if type(value) is not str:
        raise ValueError(name)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(name) from exc


def _recover(value: object, annotation: object, name: str):
    origin = get_origin(annotation)
    args = get_args(annotation)
    if annotation is Any or annotation is object:
        return value
    if annotation is datetime:
        return _datetime(value, name)
    if annotation is date:
        return _date(value, name)
    if origin in (tuple,):
        if type(value) is not list:
            raise ValueError(name)
        item_type = args[0] if args else Any
        return tuple(
            _recover(item, item_type, f"{name} item")
            for item in value
        )
    if origin in (list,):
        if type(value) is not list:
            raise ValueError(name)
        item_type = args[0] if args else Any
        return [
            _recover(item, item_type, f"{name} item")
            for item in value
        ]
    if origin in (dict, Mapping):
        if type(value) is not dict:
            raise ValueError(name)
        key_type, item_type = args if len(args) == 2 else (Any, Any)
        return {
            _recover(key, key_type, f"{name} key"):
            _recover(item, item_type, f"{name} value")
            for key, item in value.items()
        }
    if origin in (UnionType,) or str(origin) == "typing.Union":
        if value is None and type(None) in args:
            return None
        candidates = tuple(item for item in args if item is not type(None))
        for candidate in candidates:
            try:
                return _recover(value, candidate, name)
            except (TypeError, ValueError):
                continue
        raise ValueError(name)
    if isinstance(annotation, type) and is_dataclass(annotation):
        payload = _mapping(value, name)
        expected = {item.name for item in fields(annotation)}
        class_fields = {
            "SCHEMA_VERSION",
            "execution_mode",
            "broker_order_submission",
            "live_execution_eligible",
            "schema_version",
        }
        derived_fields = (
            {
                "target_reached",
                "remaining_trade_count",
            }
            if annotation is Task9MarketProgressV1
            else set()
        )
        allowed = (
            expected
            | class_fields
            | derived_fields
        )
        required = {
            item.name for item in fields(annotation)
            if item.default is MISSING and item.default_factory is MISSING
        }
        if set(payload) - allowed or not required.issubset(payload):
            raise ValueError(f"{name} fields")
        if "SCHEMA_VERSION" in payload and (
            payload["SCHEMA_VERSION"] != getattr(annotation, "SCHEMA_VERSION")
        ):
            raise ValueError(f"{name} schema")
        for class_field in (
            "execution_mode",
            "broker_order_submission",
            "live_execution_eligible",
            "schema_version",
        ):
            if (
                class_field in payload
                and class_field not in expected
                and hasattr(annotation, class_field)
                and payload[class_field]
                != getattr(annotation, class_field)
            ):
                raise ValueError(
                    f"{name} {class_field}"
                )
        hints = get_type_hints(annotation)
        try:
            result = annotation(**{
                item.name: _recover(
                    payload[item.name],
                    hints[item.name],
                    f"{name}.{item.name}",
                )
                for item in fields(annotation)
                if item.name in payload
            })
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"invalid {name}"
            ) from exc

        if annotation is Task9MarketProgressV1:
            if (
                "target_reached" in payload
                and payload["target_reached"]
                is not result.target_reached
            ):
                raise ValueError(
                    f"{name}.target_reached"
                )

            if (
                "remaining_trade_count" in payload
                and payload["remaining_trade_count"]
                != result.remaining_trade_count
            ):
                raise ValueError(
                    f"{name}.remaining_trade_count"
                )

        return result
    if annotation is float:
        if type(value) not in (int, float) or isinstance(value, bool):
            raise ValueError(name)
        return float(value)
    if annotation is int:
        if type(value) is not int or isinstance(value, bool):
            raise ValueError(name)
        return value
    if annotation is bool:
        if type(value) is not bool:
            raise ValueError(name)
        return value
    if annotation is str:
        if type(value) is not str:
            raise ValueError(name)
        return value
    return value


def dashboard_publication_snapshot_from_dict(
    value: object,
) -> DashboardPublicationSnapshotV1:
    """Recover the exact immutable snapshot, never an untyped approximation."""

    result = _recover(
        value,
        DashboardPublicationSnapshotV1,
        "dashboard publication snapshot",
    )
    if type(result) is not DashboardPublicationSnapshotV1:
        raise TypeError("dashboard publication snapshot")
    return result


class DashboardPublicationPersistentStore:
    """Durable last-known-good snapshot with strict sequence monotonicity."""

    def __init__(self, persistence_root: str | Path) -> None:
        self.root = Path(persistence_root)
        self.file_path = self.root / _FILENAME
        self._snapshot = self._read() if self.file_path.exists() else None

    def _read(self) -> DashboardPublicationSnapshotV1:
        try:
            document = json.loads(self.file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("invalid durable dashboard publication") from exc
        document = _mapping(document, "durable dashboard publication")
        if set(document) != {"schema_version", "snapshot"}:
            raise ValueError("durable dashboard publication fields")
        if document["schema_version"] != _SCHEMA_VERSION:
            raise ValueError("durable dashboard publication schema")
        return dashboard_publication_snapshot_from_dict(document["snapshot"])

    def recover(self) -> DashboardPublicationSnapshotV1 | None:
        if not self.file_path.exists():
            return None
        snapshot = self._read()
        self._snapshot = snapshot
        return snapshot

    @staticmethod
    def _sequence(snapshot: DashboardPublicationSnapshotV1) -> int:
        return 0 if snapshot.latest_envelope is None else snapshot.latest_envelope.publication_sequence

    def persist(
        self, snapshot: DashboardPublicationSnapshotV1
    ) -> DashboardPublicationSnapshotV1:
        if type(snapshot) is not DashboardPublicationSnapshotV1:
            raise TypeError("snapshot")
        current = self._snapshot
        if current is not None:
            current_sequence = self._sequence(current)
            next_sequence = self._sequence(snapshot)
            if next_sequence < current_sequence:
                raise ValueError("publication_sequence cannot move backwards")
            if next_sequence == current_sequence:
                if current.latest_envelope != snapshot.latest_envelope:
                    raise ValueError("same publication_sequence has different content")
                if (
                    current.last_attempted_publication_at is not None
                    and snapshot.last_attempted_publication_at is not None
                    and snapshot.last_attempted_publication_at
                    < current.last_attempted_publication_at
                ):
                    raise ValueError("publication attempt cannot move backwards")
        document = {"schema_version": _SCHEMA_VERSION, "snapshot": snapshot.to_dict()}
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.file_path.with_name(f"{self.file_path.name}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(document, handle, sort_keys=True, separators=(",", ":"), allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.file_path)
        finally:
            temporary.unlink(missing_ok=True)
        self._snapshot = snapshot
        return snapshot

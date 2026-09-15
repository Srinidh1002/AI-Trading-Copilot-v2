"""Durable, non-secret provenance snapshot for a Task 9 runtime config."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from services.contracts.task9_runtime_config_v1 import Task9RuntimeConfigV1


_SCHEMA_VERSION = "task9_runtime_config_snapshot.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SNAPSHOT_PREFIX = "task9-runtime-config-"
_RESOLUTIONS = frozenset({
    "EXPLICIT_CANONICAL_WINS", "LEGACY_IGNORED", "SHADOW_ONLY",
    "FAIL_IF_UNRESOLVED",
})


def _text(value: object, name: str) -> str:
    if type(value) is not str or not (value := value.strip()):
        raise ValueError(name)
    return value


def _json_value(value: Any, name: str) -> Any:
    try:
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(name) from exc
    return value


def _freeze(value: Any) -> Any:
    if value is None or type(value) in {str, int, float, bool}:
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in sorted(value.items())})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    raise ValueError("snapshot data")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def task9_runtime_config_content_sha256(config: Task9RuntimeConfigV1) -> str:
    """Return the SHA-256 of the contract's canonical JSON representation."""
    if type(config) is not Task9RuntimeConfigV1:
        raise TypeError("config")
    return hashlib.sha256(config.to_json().encode("utf-8")).hexdigest()


def validate_task9_runtime_config_snapshot_reference(
    snapshot_id: object,
    content_sha256: object,
) -> tuple[str, str]:
    """Validate a manifest-level content-addressed snapshot reference."""
    snapshot_id = _text(snapshot_id, "runtime_config_snapshot_id")
    content_sha256 = _text(content_sha256, "runtime_config_sha256")
    if not _SHA256.fullmatch(content_sha256):
        raise ValueError("runtime_config_sha256")
    if snapshot_id != f"{_SNAPSHOT_PREFIX}{content_sha256}":
        raise ValueError("runtime config snapshot reference")
    return snapshot_id, content_sha256


@dataclass(frozen=True, slots=True)
class Task9LegacyConfigConflictObservationV1:
    """Non-secret explanation of a bounded legacy capital/risk conflict."""

    field_name: str
    canonical_value: int | float | None
    legacy_source: str
    legacy_value: int | float
    legacy_representation: str
    resolution: str

    def __post_init__(self) -> None:
        if self.field_name not in {"capital", "risk_fraction"}:
            raise ValueError("field_name")
        object.__setattr__(self, "legacy_source", _text(self.legacy_source, "legacy_source"))
        if type(self.legacy_value) not in {int, float} or isinstance(self.legacy_value, bool):
            raise ValueError("legacy_value")
        if self.canonical_value is not None and (type(self.canonical_value) not in {int, float} or isinstance(self.canonical_value, bool)):
            raise ValueError("canonical_value")
        if self.legacy_representation not in {"CURRENCY", "DECIMAL_FRACTION", "PERCENT"}:
            raise ValueError("legacy_representation")
        if self.resolution not in _RESOLUTIONS:
            raise ValueError("resolution")
        if self.resolution == "EXPLICIT_CANONICAL_WINS" and self.canonical_value is None:
            raise ValueError("canonical_value")
        if self.resolution == "FAIL_IF_UNRESOLVED" and self.canonical_value is not None:
            raise ValueError("unresolved conflict cannot be marked resolved")

    def to_dict(self) -> dict[str, object]:
        return {
            "field_name": self.field_name, "canonical_value": self.canonical_value,
            "legacy_source": self.legacy_source, "legacy_value": self.legacy_value,
            "legacy_representation": self.legacy_representation,
            "resolution": self.resolution,
        }


@dataclass(frozen=True, slots=True)
class Task9RuntimeConfigSnapshotV1:
    """Immutable content-addressed snapshot; no secret material is accepted."""

    snapshot_id: str
    runtime_config_id: str
    runtime_config_version: str
    content_sha256: str
    canonical_config: Mapping[str, Any]
    conflict_observations: tuple[Task9LegacyConfigConflictObservationV1, ...] = ()
    schema_version: str = _SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError("schema_version")
        sha = _text(self.content_sha256, "content_sha256")
        if not _SHA256.fullmatch(sha):
            raise ValueError("content_sha256")
        snapshot_id, sha = validate_task9_runtime_config_snapshot_reference(
            self.snapshot_id, sha,
        )
        if not isinstance(self.canonical_config, Mapping):
            raise ValueError("canonical_config")
        raw_config = _plain(_freeze(_json_value(dict(self.canonical_config), "canonical_config")))
        try:
            config = Task9RuntimeConfigV1.from_dict(raw_config)
        except (TypeError, ValueError) as exc:
            raise ValueError("canonical_config") from exc
        if raw_config != config.to_dict():
            raise ValueError("canonical_config")
        actual_sha = task9_runtime_config_content_sha256(config)
        if actual_sha != sha:
            raise ValueError("content_sha256")
        if (self.runtime_config_id, self.runtime_config_version) != (
            config.runtime_config_id, config.runtime_config_version,
        ):
            raise ValueError("runtime config identity")
        if not isinstance(self.conflict_observations, tuple) or any(type(item) is not Task9LegacyConfigConflictObservationV1 for item in self.conflict_observations):
            raise ValueError("conflict_observations")
        identities = tuple((item.field_name, item.legacy_source, item.legacy_representation) for item in self.conflict_observations)
        if len(set(identities)) != len(identities):
            raise ValueError("conflicting legacy observation identity")
        object.__setattr__(self, "snapshot_id", snapshot_id)
        object.__setattr__(self, "content_sha256", sha)
        object.__setattr__(self, "runtime_config_id", config.runtime_config_id)
        object.__setattr__(self, "runtime_config_version", config.runtime_config_version)
        object.__setattr__(self, "canonical_config", _freeze(config.to_dict()))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version, "snapshot_id": self.snapshot_id,
            "runtime_config_id": self.runtime_config_id,
            "runtime_config_version": self.runtime_config_version,
            "content_sha256": self.content_sha256,
            "canonical_config": _plain(self.canonical_config),
            "conflict_observations": [item.to_dict() for item in self.conflict_observations],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Task9RuntimeConfigSnapshotV1":
        if not isinstance(value, Mapping):
            raise TypeError("snapshot")
        payload = dict(value)
        try:
            payload["conflict_observations"] = tuple(
                Task9LegacyConfigConflictObservationV1(**item)
                for item in payload["conflict_observations"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("snapshot serialization") from exc
        return cls(**payload)


def build_task9_runtime_config_snapshot(
    config: Task9RuntimeConfigV1,
    *,
    conflict_observations: tuple[Task9LegacyConfigConflictObservationV1, ...] = (),
) -> Task9RuntimeConfigSnapshotV1:
    """Build one deterministic non-secret snapshot without altering the builder."""
    sha = task9_runtime_config_content_sha256(config)
    return Task9RuntimeConfigSnapshotV1(
        snapshot_id=f"{_SNAPSHOT_PREFIX}{sha}",
        runtime_config_id=config.runtime_config_id,
        runtime_config_version=config.runtime_config_version,
        content_sha256=sha,
        canonical_config=config.to_dict(),
        conflict_observations=conflict_observations,
    )

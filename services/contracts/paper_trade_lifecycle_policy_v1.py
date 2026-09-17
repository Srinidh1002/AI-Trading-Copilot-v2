"""Immutable, PAPER-only controls for a future paper-trade lifecycle."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

ENTRY_ACTIVATION_MODES = frozenset({"ZONE_TOUCH", "PREFERRED_ENTRY_TOUCH", "ZONE_CLOSE"})
TRIGGER_MODES = frozenset({"TOUCH", "CLOSE"})
SAME_OBSERVATION_PRECEDENCE = frozenset({"STOP_FIRST", "TARGET_FIRST", "CONSERVATIVE_STOP_FIRST"})
MULTIPLE_TARGET_CROSSING_MODES = frozenset({"HIGHEST_CROSSED_TARGET", "SEQUENTIAL_TARGETS"})
RUNNER_CLOSE_MODES = frozenset({"TARGET_3", "SESSION_END", "EXPIRY", "EXPLICIT_SIGNAL"})


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not (value := value.strip()):
        raise ValueError(name)
    return value


def _duration(value: Any, name: str) -> int:
    if type(value) is not int or isinstance(value, bool) or value <= 0:
        raise ValueError(name)
    return value


def _fraction(value: Any, name: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(name)
    return float(value)


def _freeze(value: Any) -> Any:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType(dict(sorted((_text(key, "metadata key"), _freeze(item)) for key, item in value.items())))
    if type(value) in (tuple, list):
        return tuple(_freeze(item) for item in value)
    raise ValueError("metadata")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class PaperTradeLifecyclePolicyV1:
    lifecycle_policy_id: str
    policy_timestamp: datetime
    policy_source: str
    entry_activation_mode: str = "ZONE_TOUCH"
    entry_zone_tolerance_fraction: float = 0.0
    entry_timeout_seconds: int = 1
    allow_gap_entry: bool = False
    require_fresh_observation: bool = True
    maximum_observation_age_seconds: int = 1
    stop_trigger_mode: str = "TOUCH"
    target_trigger_mode: str = "TOUCH"
    same_observation_precedence: str = "CONSERVATIVE_STOP_FIRST"
    multiple_target_crossing_mode: str = "SEQUENTIAL_TARGETS"
    allow_partial_exits: bool = False
    runner_enabled: bool = False
    runner_close_mode: str = "TARGET_3"
    close_at_session_end: bool = True
    close_at_expiry: bool = True
    maximum_holding_seconds: int = 1
    reject_duplicate_observation: bool = True
    reject_out_of_order_observation: bool = True
    warnings: tuple[str, ...] = ()
    source_timestamps: Mapping[str, datetime] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "lifecycle_policy_id", _text(self.lifecycle_policy_id, "lifecycle_policy_id"))
        object.__setattr__(self, "policy_source", _text(self.policy_source, "policy_source"))
        if not isinstance(self.policy_timestamp, datetime) or self.policy_timestamp.tzinfo is None:
            raise ValueError("policy_timestamp")
        for field_name, allowed in (("entry_activation_mode", ENTRY_ACTIVATION_MODES), ("stop_trigger_mode", TRIGGER_MODES), ("target_trigger_mode", TRIGGER_MODES), ("same_observation_precedence", SAME_OBSERVATION_PRECEDENCE), ("multiple_target_crossing_mode", MULTIPLE_TARGET_CROSSING_MODES), ("runner_close_mode", RUNNER_CLOSE_MODES)):
            if getattr(self, field_name) not in allowed:
                raise ValueError(field_name)
        object.__setattr__(self, "entry_zone_tolerance_fraction", _fraction(self.entry_zone_tolerance_fraction, "entry_zone_tolerance_fraction"))
        for field_name in ("entry_timeout_seconds", "maximum_observation_age_seconds", "maximum_holding_seconds"):
            object.__setattr__(self, field_name, _duration(getattr(self, field_name), field_name))
        for field_name in ("allow_gap_entry", "require_fresh_observation", "allow_partial_exits", "runner_enabled", "close_at_session_end", "close_at_expiry", "reject_duplicate_observation", "reject_out_of_order_observation"):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(field_name)
        if self.runner_enabled and not self.allow_partial_exits:
            raise ValueError("runner requires partial exits")
        if self.maximum_holding_seconds < self.entry_timeout_seconds:
            raise ValueError("maximum_holding_seconds")
        if not isinstance(self.warnings, tuple):
            raise TypeError("warnings")
        object.__setattr__(self, "warnings", tuple(dict.fromkeys(_text(item, "warning") for item in self.warnings)))
        if not isinstance(self.source_timestamps, Mapping) or any(type(key) is not str or not key.strip() or not isinstance(value, datetime) or value.tzinfo is None for key, value in self.source_timestamps.items()):
            raise ValueError("source_timestamps")
        object.__setattr__(self, "source_timestamps", MappingProxyType(dict(sorted(self.source_timestamps.items()))))
        object.__setattr__(self, "metadata", _freeze(self.metadata))
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.schema_version != "1.0":
            raise ValueError("paper")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        result["policy_timestamp"] = self.policy_timestamp.isoformat()
        result["source_timestamps"] = {key: value.isoformat() for key, value in self.source_timestamps.items()}
        result["warnings"] = list(self.warnings)
        result["metadata"] = _plain(self.metadata)
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        for name in ("lifecycle_policy_id", "policy_timestamp", "source_timestamps"):
            result.pop(name)
        return result

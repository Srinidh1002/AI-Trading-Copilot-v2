"""Immutable, PAPER-only result of deterministic entry-zone evaluation."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from services.core.market_identity import normalize_market_identity


_DIRECTION_TO_OPTION_RIGHT = {"BULLISH": "CALL", "BEARISH": "PUT"}
_ENTRY_METHODS = frozenset(
    {"OPTION_MID", "OPTION_ASK", "LAST_TRADED_PRICE", "SIGNAL_REFERENCE", "HYBRID"}
)
_REFERENCE_SOURCES = frozenset(
    {"OPTION_MID", "OPTION_ASK", "LAST_TRADED_PRICE", "SIGNAL_REFERENCE"}
)
_STATUSES = frozenset({"READY", "BLOCKED", "NO_ENTRY"})


def _nonblank_string(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value


def _aware_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value


def _optional_positive_number(value: object, name: str) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite number greater than zero")
    return float(value)


def _optional_fraction(value: object, name: str, *, maximum: float | None = 1.0) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} exceeds its permitted maximum")
    return float(value)


def _diagnostics(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    normalized: list[str] = []
    for item in value:
        if type(item) is not str:
            raise TypeError(f"{name} entries must be strings")
        item = item.strip()
        if not item:
            raise ValueError(f"{name} entries must be nonblank")
        if item not in normalized:
            normalized.append(item)
    return tuple(normalized)


def _source_timestamps(value: object) -> Mapping[str, datetime]:
    if not isinstance(value, Mapping):
        raise TypeError("source_timestamps must be a mapping")
    timestamps: dict[str, datetime] = {}
    for key, timestamp in value.items():
        if type(key) is not str or not key.strip():
            raise ValueError("source_timestamps keys must be nonblank strings")
        timestamps[key] = _aware_datetime(timestamp, "source_timestamps values")
    return MappingProxyType(dict(sorted(timestamps.items())))


def _freeze_metadata(value: object) -> Any:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("metadata must be JSON-safe")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("metadata keys must be strings")
            frozen[key] = _freeze_metadata(item)
        return MappingProxyType(dict(sorted(frozen.items())))
    if type(value) in (list, tuple):
        return tuple(_freeze_metadata(item) for item in value)
    raise ValueError("metadata must be JSON-safe")


def _metadata(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("metadata must be a mapping")
    return _freeze_metadata(value)


def _plain_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain_json_value(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain_json_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class EntryZoneEvaluationResultV1:
    evaluation_result_id: str
    evaluation_id: str
    evaluated_at: datetime
    underlying_symbol: str
    exchange: str
    direction: str
    option_right: str
    entry_method: str
    selected_reference_source: str | None
    status: str
    entry_reference_price: float | None
    entry_zone_lower: float | None
    entry_zone_upper: float | None
    entry_tolerance_fraction: float | None
    maximum_chase_price: float | None
    maximum_entry_premium: float | None
    effective_spread_fraction: float | None
    effective_spread_limit: float | None
    require_limit_entry: bool
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    source_timestamps: Mapping[str, datetime] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in ("evaluation_result_id", "evaluation_id"):
            object.__setattr__(self, name, _nonblank_string(getattr(self, name), name))
        object.__setattr__(self, "evaluated_at", _aware_datetime(self.evaluated_at, "evaluated_at"))

        identity = normalize_market_identity(self.underlying_symbol, self.exchange)
        if identity is None:
            raise ValueError("underlying_symbol and exchange must be a supported canonical identity")
        object.__setattr__(self, "underlying_symbol", identity[0])
        object.__setattr__(self, "exchange", identity[1])

        if type(self.direction) is not str or self.direction not in _DIRECTION_TO_OPTION_RIGHT:
            raise ValueError("direction must be BULLISH or BEARISH")
        if type(self.option_right) is not str or self.option_right not in {"CALL", "PUT"}:
            raise ValueError("option_right must be CALL or PUT")
        if self.option_right != _DIRECTION_TO_OPTION_RIGHT[self.direction]:
            raise ValueError("direction and option_right must agree")
        if type(self.entry_method) is not str or self.entry_method not in _ENTRY_METHODS:
            raise ValueError("entry_method is unsupported")
        if self.selected_reference_source is not None:
            if type(self.selected_reference_source) is not str or self.selected_reference_source not in _REFERENCE_SOURCES:
                raise ValueError("selected_reference_source is unsupported")
        if type(self.status) is not str or self.status not in _STATUSES:
            raise ValueError("status is unsupported")

        for name in (
            "entry_reference_price",
            "entry_zone_lower",
            "entry_zone_upper",
            "maximum_chase_price",
            "maximum_entry_premium",
        ):
            object.__setattr__(self, name, _optional_positive_number(getattr(self, name), name))
        object.__setattr__(
            self,
            "entry_tolerance_fraction",
            _optional_fraction(self.entry_tolerance_fraction, "entry_tolerance_fraction"),
        )
        object.__setattr__(
            self,
            "effective_spread_fraction",
            _optional_fraction(self.effective_spread_fraction, "effective_spread_fraction", maximum=None),
        )
        object.__setattr__(
            self,
            "effective_spread_limit",
            _optional_fraction(self.effective_spread_limit, "effective_spread_limit"),
        )
        if type(self.require_limit_entry) is not bool:
            raise TypeError("require_limit_entry must be a bool")

        object.__setattr__(self, "blockers", _diagnostics(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _diagnostics(self.warnings, "warnings"))
        object.__setattr__(self, "decision_reasons", _diagnostics(self.decision_reasons, "decision_reasons"))
        object.__setattr__(self, "source_timestamps", _source_timestamps(self.source_timestamps))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

        price_group = (
            self.selected_reference_source,
            self.entry_reference_price,
            self.entry_zone_lower,
            self.entry_zone_upper,
            self.entry_tolerance_fraction,
            self.maximum_chase_price,
        )
        if all(value is None for value in price_group):
            price_group_complete = False
        elif any(value is None for value in price_group):
            raise ValueError("price group must be wholly absent or complete")
        else:
            price_group_complete = True
            if not self.entry_zone_lower < self.entry_zone_upper:
                raise ValueError("entry_zone_lower must be below entry_zone_upper")
            if not self.entry_zone_lower <= self.entry_reference_price <= self.entry_zone_upper:
                raise ValueError("entry_reference_price must be inside the entry zone")
            if self.maximum_chase_price < self.entry_zone_upper:
                raise ValueError("maximum_chase_price must not be below entry_zone_upper")

        if self.status == "READY":
            if not price_group_complete or self.blockers:
                raise ValueError("READY requires complete geometry and no blockers")
            if self.maximum_entry_premium is not None and (
                self.entry_reference_price > self.maximum_entry_premium
                or self.entry_zone_upper > self.maximum_entry_premium
                or self.maximum_chase_price > self.maximum_entry_premium
            ):
                raise ValueError("READY geometry exceeds maximum_entry_premium")
            if (
                self.effective_spread_fraction is not None
                and self.effective_spread_limit is not None
                and self.effective_spread_fraction > self.effective_spread_limit
            ):
                raise ValueError("READY effective spread exceeds its limit")
        elif self.status == "BLOCKED" and not self.blockers:
            raise ValueError("BLOCKED requires blockers")
        elif self.status == "NO_ENTRY" and not self.decision_reasons:
            raise ValueError("NO_ENTRY requires decision_reasons")

        if type(self.execution_mode) is not str or self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible is not False:
            raise ValueError("live_execution_eligible must be False")
        if type(self.schema_version) is not str or self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    @property
    def zone_width(self) -> float | None:
        if self.entry_zone_lower is None:
            return None
        return self.entry_zone_upper - self.entry_zone_lower

    @property
    def lower_distance_fraction(self) -> float | None:
        if self.entry_reference_price is None:
            return None
        return (self.entry_reference_price - self.entry_zone_lower) / self.entry_reference_price

    @property
    def upper_distance_fraction(self) -> float | None:
        if self.entry_reference_price is None:
            return None
        return (self.entry_zone_upper - self.entry_reference_price) / self.entry_reference_price

    @property
    def spread_within_limit(self) -> bool | None:
        if self.effective_spread_fraction is None or self.effective_spread_limit is None:
            return None
        return self.effective_spread_fraction <= self.effective_spread_limit

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_result_id": self.evaluation_result_id,
            "evaluation_id": self.evaluation_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "underlying_symbol": self.underlying_symbol,
            "exchange": self.exchange,
            "direction": self.direction,
            "option_right": self.option_right,
            "entry_method": self.entry_method,
            "selected_reference_source": self.selected_reference_source,
            "status": self.status,
            "entry_reference_price": self.entry_reference_price,
            "entry_zone_lower": self.entry_zone_lower,
            "entry_zone_upper": self.entry_zone_upper,
            "entry_tolerance_fraction": self.entry_tolerance_fraction,
            "maximum_chase_price": self.maximum_chase_price,
            "maximum_entry_premium": self.maximum_entry_premium,
            "effective_spread_fraction": self.effective_spread_fraction,
            "effective_spread_limit": self.effective_spread_limit,
            "require_limit_entry": self.require_limit_entry,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "decision_reasons": list(self.decision_reasons),
            "source_timestamps": {
                key: timestamp.isoformat() for key, timestamp in self.source_timestamps.items()
            },
            "metadata": _plain_json_value(self.metadata),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def semantic_dict(self) -> dict[str, Any]:
        value = self.to_dict()
        for field_name in (
            "evaluation_result_id",
            "evaluation_id",
            "evaluated_at",
            "source_timestamps",
        ):
            value.pop(field_name)
        return value

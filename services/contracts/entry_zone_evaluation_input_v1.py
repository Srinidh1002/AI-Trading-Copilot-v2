"""Immutable, PAPER-only input for deterministic entry-zone evaluation."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from services.core.market_identity import normalize_market_identity


_DIRECTION_TO_OPTION_RIGHT = {"BULLISH": "CALL", "BEARISH": "PUT"}
_ENTRY_REFERENCE_METHODS = frozenset(
    {"OPTION_MID", "OPTION_ASK", "LAST_TRADED_PRICE", "SIGNAL_REFERENCE", "HYBRID"}
)


def _nonblank_string(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value


def _aware_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value


def _positive_optional_number(value: object, name: str) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite number greater than zero")
    return float(value)


def _optional_fraction(value: object, name: str) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a finite fraction from zero through one")
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
class EntryZoneEvaluationInputV1:
    evaluation_id: str
    evaluation_result_id: str
    evaluated_at: datetime
    underlying_symbol: str
    exchange: str
    trade_plan_input_id: str
    policy_id: str
    direction: str
    option_right: str
    entry_reference_method: str
    last_traded_price: float | None
    bid_price: float | None
    ask_price: float | None
    signal_reference_price: float | None
    option_mid_price: float | None
    option_quote_timestamp: datetime
    maximum_entry_premium: float | None
    maximum_spread_fraction: float | None
    planning_allowed: bool
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source_timestamps: Mapping[str, datetime] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in ("evaluation_id", "evaluation_result_id", "trade_plan_input_id", "policy_id"):
            object.__setattr__(self, name, _nonblank_string(getattr(self, name), name))

        object.__setattr__(self, "evaluated_at", _aware_datetime(self.evaluated_at, "evaluated_at"))
        object.__setattr__(
            self,
            "option_quote_timestamp",
            _aware_datetime(self.option_quote_timestamp, "option_quote_timestamp"),
        )

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
        if type(self.entry_reference_method) is not str or self.entry_reference_method not in _ENTRY_REFERENCE_METHODS:
            raise ValueError("entry_reference_method is unsupported")

        for name in (
            "last_traded_price",
            "bid_price",
            "ask_price",
            "signal_reference_price",
            "option_mid_price",
            "maximum_entry_premium",
        ):
            object.__setattr__(self, name, _positive_optional_number(getattr(self, name), name))
        object.__setattr__(
            self,
            "maximum_spread_fraction",
            _optional_fraction(self.maximum_spread_fraction, "maximum_spread_fraction"),
        )

        if self.bid_price is not None and self.ask_price is not None and self.bid_price > self.ask_price:
            raise ValueError("bid_price cannot exceed ask_price")
        if (
            self.bid_price is not None
            and self.ask_price is not None
            and self.option_mid_price is not None
            and not self.bid_price <= self.option_mid_price <= self.ask_price
        ):
            raise ValueError("option_mid_price must be between bid_price and ask_price")

        if type(self.planning_allowed) is not bool:
            raise TypeError("planning_allowed must be a bool")
        object.__setattr__(self, "blockers", _diagnostics(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _diagnostics(self.warnings, "warnings"))
        object.__setattr__(self, "source_timestamps", _source_timestamps(self.source_timestamps))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

        if type(self.execution_mode) is not str or self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible is not False:
            raise ValueError("live_execution_eligible must be False")
        if type(self.schema_version) is not str or self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "evaluation_result_id": self.evaluation_result_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "underlying_symbol": self.underlying_symbol,
            "exchange": self.exchange,
            "trade_plan_input_id": self.trade_plan_input_id,
            "policy_id": self.policy_id,
            "direction": self.direction,
            "option_right": self.option_right,
            "entry_reference_method": self.entry_reference_method,
            "last_traded_price": self.last_traded_price,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "signal_reference_price": self.signal_reference_price,
            "option_mid_price": self.option_mid_price,
            "option_quote_timestamp": self.option_quote_timestamp.isoformat(),
            "maximum_entry_premium": self.maximum_entry_premium,
            "maximum_spread_fraction": self.maximum_spread_fraction,
            "planning_allowed": self.planning_allowed,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
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
            "evaluation_id",
            "evaluation_result_id",
            "evaluated_at",
            "source_timestamps",
        ):
            value.pop(field_name)
        return value

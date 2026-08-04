"""Immutable, redacted INDIA_VIX capture evidence for a PAPER cycle."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from services.contracts.market_data_provenance_v1 import MarketDataProvenanceV1

_STATUSES = frozenset(("READY", "UNAVAILABLE", "STALE", "BLOCKED"))
_SECRET_WORDS = ("secret", "password", "pin", "jwt", "totp", "authorization", "session", "feed")


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must be a tuple of non-empty strings")
    result = tuple(value)
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def _safe_metadata(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("metadata must be a mapping")
    result: dict[str, Any] = {}
    for key, item in sorted(value.items()):
        name = str(key)
        if any(word in name.lower() for word in _SECRET_WORDS):
            raise ValueError("metadata must not contain credentials")
        if isinstance(item, Mapping):
            result[name] = _safe_metadata(item)
        elif item is None or isinstance(item, (str, bool, int, float)):
            result[name] = item
        else:
            raise TypeError("metadata must contain JSON scalar values")
    return MappingProxyType(result)


@dataclass(frozen=True, slots=True)
class IndiaVixCaptureResultV1:
    capture_id: str
    cycle_id: str
    canonical_name: str
    provider: str
    provider_symbol: str | None
    provider_exchange: str | None
    provider_token: str | None
    instrument_type: str | None
    current_value: float | None
    previous_close: float | None
    provider_timestamp: datetime | None
    evaluated_at: datetime
    provenance: MarketDataProvenanceV1
    source_status: str
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "india_vix_capture_result.v1"

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value.strip() for value in (self.capture_id, self.cycle_id, self.provider)):
            raise ValueError("capture IDs and provider must be non-empty")
        if self.canonical_name != "INDIA_VIX" or self.source_status not in _STATUSES:
            raise ValueError("invalid India VIX identity or status")
        if self.execution_mode not in {"PAPER", "MANUAL_LIVE"} or self.live_execution_eligible is not False:
            raise ValueError("India VIX capture cannot enable automated live execution")
        if self.schema_version != "india_vix_capture_result.v1" or type(self.provenance) is not MarketDataProvenanceV1:
            raise ValueError("invalid India VIX capture contract")
        _aware(self.evaluated_at, "evaluated_at")
        if self.provider_timestamp is not None:
            _aware(self.provider_timestamp, "provider_timestamp")
        for value in (self.current_value, self.previous_close):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value <= 0):
                raise ValueError("India VIX values must be finite and positive")
        if self.source_status == "READY":
            if (self.provider_symbol, self.provider_exchange, self.instrument_type) != ("India VIX", "NSE", "AMXIDX"):
                raise ValueError("India VIX provider identity is invalid")
            if not self.provider_token or self.provider_timestamp is None or self.current_value is None or self.previous_close is None:
                raise ValueError("ready India VIX evidence is incomplete")
        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))
        object.__setattr__(self, "metadata", _safe_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id, "cycle_id": self.cycle_id, "canonical_name": self.canonical_name,
            "provider": self.provider, "provider_symbol": self.provider_symbol, "provider_exchange": self.provider_exchange,
            "provider_token": self.provider_token, "instrument_type": self.instrument_type,
            "current_value": self.current_value, "previous_close": self.previous_close,
            "provider_timestamp": self.provider_timestamp.isoformat() if self.provider_timestamp else None,
            "evaluated_at": self.evaluated_at.isoformat(), "provenance": self.provenance.to_dict(),
            "source_status": self.source_status, "blockers": list(self.blockers), "warnings": list(self.warnings),
            "metadata": dict(self.metadata), "execution_mode": self.execution_mode,
            "live_execution_eligible": False, "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

"""Immutable provider-agnostic contract for one scheduled market event."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES, normalize_market_identity


EVENT_CATEGORIES = frozenset({
    "RBI_POLICY", "CPI", "WPI", "GDP", "UNION_BUDGET", "ELECTION",
    "EXCHANGE_HOLIDAY", "SPECIAL_SESSION", "WEEKLY_EXPIRY", "MONTHLY_EXPIRY",
    "ROLLOVER", "OTHER_SCHEDULED_MACRO",
})
CONFIRMATION_STATES = frozenset({"CONFIRMED", "TENTATIVE", "UNAVAILABLE"})
EVENT_STATUSES = frozenset({
    "UPCOMING", "ACTIVE", "COMPLETED", "CANCELLED", "POSTPONED", "UNAVAILABLE", "BLOCKED",
})
SEVERITIES = frozenset({"LOW", "MODERATE", "HIGH", "EXTREME", "UNAVAILABLE"})
SESSION_OVERRIDE_STATES = frozenset({
    "NONE", "MARKET_CLOSED", "SPECIAL_SESSION", "MODIFIED_SESSION", "UNAVAILABLE",
})
EXCHANGES = frozenset({"NSE", "BSE"})
_MACRO_WITH_NO_SESSION_OVERRIDE = frozenset({"RBI_POLICY", "CPI", "WPI", "GDP"})
_EXPIRY_OR_ROLLOVER = frozenset({"WEEKLY_EXPIRY", "MONTHLY_EXPIRY", "ROLLOVER"})


def _text(value: object, name: str, *, upper: bool = False, maximum: int | None = None) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    value = " ".join(value.split())
    if not value:
        raise ValueError(f"{name} must not be empty")
    if maximum is not None and len(value) > maximum:
        raise ValueError(f"{name} is too long")
    return value.upper() if upper else value


def _aware_time(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    normalized = tuple(_text(item, f"{name} item", maximum=240) for item in value)
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{name} must not contain duplicates")
    return normalized


def _metadata(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("metadata must be a mapping")
    try:
        normalized = json.loads(json.dumps(dict(value), sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata must be JSON-safe") from exc
    return _freeze_metadata(normalized)


def _freeze_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_metadata(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_metadata(item) for item in value)
    return value


def _thaw_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_metadata(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_metadata(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class ScheduledMarketEventV1:
    scheduled_market_event_id: str
    created_at: datetime
    event_name: str
    event_category: str
    scheduled_start: datetime
    scheduled_end: datetime | None
    source_id: str
    source_timestamp: datetime
    confirmation_state: str
    event_status: str
    severity: str
    affected_market_identities: tuple[tuple[str, str], ...]
    affected_exchanges: tuple[str, ...]
    analysis_allowed: bool
    new_entries_allowed: bool
    session_override_state: str
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "scheduled_market_event.v1"

    def __post_init__(self) -> None:
        for name in ("scheduled_market_event_id", "source_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name, maximum=160))
        event_name = _text(self.event_name, "event_name", maximum=160)
        if "<" in event_name or ">" in event_name:
            raise ValueError("event_name must be a short canonical label without HTML")
        object.__setattr__(self, "event_name", event_name)

        for name in ("created_at", "scheduled_start", "source_timestamp"):
            object.__setattr__(self, name, _aware_time(getattr(self, name), name))
        if self.scheduled_end is not None:
            object.__setattr__(self, "scheduled_end", _aware_time(self.scheduled_end, "scheduled_end"))
            if self.scheduled_end < self.scheduled_start:
                raise ValueError("scheduled_end must not be before scheduled_start")

        for name, allowed in (
            ("event_category", EVENT_CATEGORIES),
            ("confirmation_state", CONFIRMATION_STATES),
            ("event_status", EVENT_STATUSES),
            ("severity", SEVERITIES),
            ("session_override_state", SESSION_OVERRIDE_STATES),
        ):
            normalized = _text(getattr(self, name), name, upper=True)
            if normalized not in allowed:
                raise ValueError(f"unsupported {name}")
            object.__setattr__(self, name, normalized)

        if not isinstance(self.analysis_allowed, bool) or not isinstance(self.new_entries_allowed, bool):
            raise TypeError("analysis_allowed and new_entries_allowed must be boolean")
        if not self.analysis_allowed and self.new_entries_allowed:
            raise ValueError("new_entries_allowed requires analysis_allowed")

        identities = self._normalize_identities(self.affected_market_identities)
        exchanges = self._normalize_exchanges(self.affected_exchanges)
        if any(exchange not in exchanges for _, exchange in identities):
            raise ValueError("affected identity exchange must be listed in affected_exchanges")
        object.__setattr__(self, "affected_market_identities", identities)
        object.__setattr__(self, "affected_exchanges", exchanges)
        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("scheduled market event is paper-only")
        if self.schema_version != "scheduled_market_event.v1":
            raise ValueError("unsupported scheduled market event schema")

        self._validate_category_compatibility()
        self._validate_state_consistency()

    @staticmethod
    def _normalize_identities(value: object) -> tuple[tuple[str, str], ...]:
        if not isinstance(value, tuple):
            raise TypeError("affected_market_identities must be a tuple")
        normalized: list[tuple[str, str]] = []
        for item in value:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("affected market identity must be a pair")
            identity = normalize_market_identity(*item)
            if identity not in SUPPORTED_MARKET_IDENTITIES:
                raise ValueError("unsupported affected market identity")
            normalized.append(identity)
        result = tuple(normalized)
        if len(result) != len(set(result)) or result != tuple(sorted(result)):
            raise ValueError("affected identities must be unique and ordered")
        return result

    @staticmethod
    def _normalize_exchanges(value: object) -> tuple[str, ...]:
        if not isinstance(value, tuple):
            raise TypeError("affected_exchanges must be a tuple")
        normalized = tuple(_text(item, "affected_exchanges item", upper=True) for item in value)
        if any(item not in EXCHANGES for item in normalized):
            raise ValueError("unsupported affected exchange")
        if len(normalized) != len(set(normalized)) or normalized != tuple(sorted(normalized)):
            raise ValueError("affected exchanges must be unique and ordered")
        return normalized

    def _validate_category_compatibility(self) -> None:
        category = self.event_category
        override = self.session_override_state
        if category in {"RBI_POLICY", "UNION_BUDGET"} and self.severity not in {"HIGH", "EXTREME"}:
            raise ValueError(f"{category} requires HIGH or EXTREME severity")
        if category == "EXCHANGE_HOLIDAY":
            if not self.affected_exchanges or override != "MARKET_CLOSED" or self.new_entries_allowed:
                raise ValueError("EXCHANGE_HOLIDAY requires exchanges, MARKET_CLOSED, and blocked entries")
        elif category == "SPECIAL_SESSION":
            if not self.affected_exchanges or override not in {"SPECIAL_SESSION", "MODIFIED_SESSION"}:
                raise ValueError("SPECIAL_SESSION requires exchanges and a special session override")
        elif category in {"WEEKLY_EXPIRY", "MONTHLY_EXPIRY"}:
            if not self.affected_market_identities or not self.affected_exchanges or override != "NONE":
                raise ValueError("expiry events require identities, exchanges, and NONE override")
        elif category == "ROLLOVER":
            if not self.affected_market_identities or override != "NONE":
                raise ValueError("ROLLOVER requires identities and NONE override")
        elif category in _MACRO_WITH_NO_SESSION_OVERRIDE and override != "NONE":
            raise ValueError("macro events require NONE session override")
        elif category in {"UNION_BUDGET", "ELECTION", "OTHER_SCHEDULED_MACRO"} and override == "MARKET_CLOSED":
            raise ValueError("macro events cannot assert MARKET_CLOSED")
        if category in _EXPIRY_OR_ROLLOVER and self.severity == "UNAVAILABLE":
            raise ValueError("scheduled expiry or rollover cannot use UNAVAILABLE severity")

    def _validate_state_consistency(self) -> None:
        if self.confirmation_state == "TENTATIVE" and not self.warnings:
            raise ValueError("TENTATIVE requires warnings")
        if self.confirmation_state == "UNAVAILABLE":
            if self.event_status in {"UPCOMING", "ACTIVE"}:
                raise ValueError("UNAVAILABLE confirmation cannot claim UPCOMING or ACTIVE")
            if not self.warnings and not self.blockers:
                raise ValueError("UNAVAILABLE confirmation requires warnings or blockers")
        if self.event_status == "POSTPONED" and not self.warnings:
            raise ValueError("POSTPONED requires warnings")
        if self.event_status == "BLOCKED" and not self.blockers:
            raise ValueError("BLOCKED requires blockers")
        if self.event_status == "UNAVAILABLE" and not self.blockers and (not self.analysis_allowed or not self.new_entries_allowed):
            raise ValueError("UNAVAILABLE cannot imply restrictions without blockers")
        if self.event_status in {"CANCELLED", "COMPLETED"} and not self.blockers and (not self.analysis_allowed or not self.new_entries_allowed):
            raise ValueError("cancelled or completed events require explicit blockers for restrictions")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        for name in ("created_at", "scheduled_start", "source_timestamp"):
            result[name] = result[name].isoformat()
        result["scheduled_end"] = self.scheduled_end.isoformat() if self.scheduled_end else None
        result["affected_market_identities"] = [list(item) for item in self.affected_market_identities]
        result["affected_exchanges"] = list(self.affected_exchanges)
        result["blockers"] = list(self.blockers)
        result["warnings"] = list(self.warnings)
        result["metadata"] = _thaw_metadata(self.metadata)
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        result.pop("scheduled_market_event_id")
        result.pop("created_at")
        return result

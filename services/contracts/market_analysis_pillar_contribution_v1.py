"""Immutable, provider-free provenance records for the fourteen analysis pillars."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from services.analysis.market_analysis_pillar_aggregation import PILLAR_ORDER


_IDENTITIES = frozenset({("NIFTY", "NSE"), ("SENSEX", "BSE")})
_STATUSES = frozenset({"READY", "UNAVAILABLE", "BLOCKED", "CONFLICTING"})
_DIRECTIONS = frozenset({"BULLISH", "BEARISH", "NEUTRAL", "UNAVAILABLE", "CONFLICTING"})
_PROVENANCE = frozenset({"DIRECT", "DERIVED", "GROUPED", "UNAVAILABLE"})
_FORBIDDEN_METADATA = frozenset({"api_key", "apikey", "secret", "password", "pin", "authorization", "access_token", "refresh_token", "jwt", "raw_payload", "provider_payload", "raw_exception", "exception_text"})


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (clean := value.strip()):
        raise ValueError(name)
    return clean


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    output: list[str] = []
    for item in value:
        message = _text(item, name)
        if message in output:
            raise ValueError(f"duplicate {name}")
        output.append(message)
    return tuple(output)


def _metadata(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("metadata")
    copied = dict(value)
    def safe(item: object) -> bool:
        if isinstance(item, Mapping):
            return all(isinstance(key, str) and key.strip().lower() not in _FORBIDDEN_METADATA and safe(child) for key, child in item.items())
        if isinstance(item, (list, tuple)):
            return all(safe(child) for child in item)
        return True
    if not safe(copied):
        raise ValueError("credential-like metadata")
    try:
        json.dumps(copied, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata must be safe JSON") from exc
    return MappingProxyType(copied)


@dataclass(frozen=True, slots=True)
class MarketAnalysisPillarContributionV1:
    """One honest contribution record; missing metrics stay explicitly missing."""

    contribution_id: str
    pillar_name: str
    underlying_symbol: str
    exchange: str
    cycle_id: str
    observation_id: str
    status: str
    direction: str
    raw_score: float | None
    normalized_score: float | None
    source_contract_type: str | None
    source_result_id: str | None
    source_provider_id: str | None
    source_timestamp: datetime | None
    evaluated_at: datetime
    provenance_classification: str
    contribution_available: bool
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "market_analysis_pillar_contribution.v1"

    def __post_init__(self) -> None:
        for name in ("contribution_id", "cycle_id", "observation_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        pillar = _text(self.pillar_name, "pillar_name")
        if pillar not in PILLAR_ORDER:
            raise ValueError("unsupported pillar_name")
        object.__setattr__(self, "pillar_name", pillar)
        identity = (_text(self.underlying_symbol, "underlying_symbol").upper(), _text(self.exchange, "exchange").upper())
        if identity not in _IDENTITIES:
            raise ValueError("unsupported market identity")
        object.__setattr__(self, "underlying_symbol", identity[0]); object.__setattr__(self, "exchange", identity[1])
        status = _text(self.status, "status").upper()
        direction = _text(self.direction, "direction").upper()
        provenance = _text(self.provenance_classification, "provenance_classification").upper()
        if status not in _STATUSES or direction not in _DIRECTIONS or provenance not in _PROVENANCE:
            raise ValueError("controlled contribution vocabulary")
        if not isinstance(self.contribution_available, bool) or self.contribution_available != (status == "READY"):
            raise ValueError("contribution availability must agree with status")
        if not self.contribution_available and direction != "UNAVAILABLE":
            raise ValueError("unavailable contribution direction")
        for name in ("raw_score", "normalized_score"):
            score = getattr(self, name)
            if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float)) or not isfinite(float(score))):
                raise ValueError(name)
            if score is not None: object.__setattr__(self, name, float(score))
        if self.raw_score is not None and not -1.0 <= self.raw_score <= 1.0:
            raise ValueError("raw_score bounds")
        if self.normalized_score is not None and not 0.0 <= self.normalized_score <= 1.0:
            raise ValueError("normalized_score bounds")
        if self.contribution_available and (not self.source_contract_type or not self.source_result_id):
            raise ValueError("available contribution requires typed source")
        for name in ("source_contract_type", "source_result_id", "source_provider_id"):
            value = getattr(self, name)
            if value is not None: object.__setattr__(self, name, _text(value, name))
        if self.source_timestamp is not None: _aware(self.source_timestamp, "source_timestamp")
        _aware(self.evaluated_at, "evaluated_at")
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.schema_version != "market_analysis_pillar_contribution.v1":
            raise ValueError("PAPER-only contribution")
        object.__setattr__(self, "status", status); object.__setattr__(self, "direction", direction); object.__setattr__(self, "provenance_classification", provenance)
        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers")); object.__setattr__(self, "warnings", _messages(self.warnings, "warnings")); object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, object]:
        return {"contribution_id": self.contribution_id, "pillar_name": self.pillar_name, "underlying_symbol": self.underlying_symbol, "exchange": self.exchange, "cycle_id": self.cycle_id, "observation_id": self.observation_id, "status": self.status, "direction": self.direction, "raw_score": self.raw_score, "normalized_score": self.normalized_score, "source_contract_type": self.source_contract_type, "source_result_id": self.source_result_id, "source_provider_id": self.source_provider_id, "source_timestamp": self.source_timestamp.isoformat() if self.source_timestamp else None, "evaluated_at": self.evaluated_at.isoformat(), "provenance_classification": self.provenance_classification, "contribution_available": self.contribution_available, "blockers": list(self.blockers), "warnings": list(self.warnings), "metadata": dict(self.metadata), "execution_mode": self.execution_mode, "live_execution_eligible": self.live_execution_eligible, "schema_version": self.schema_version}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True, slots=True)
class MarketAnalysisPillarContributionCollectionV1:
    cycle_id: str
    observation_id: str
    underlying_symbol: str
    exchange: str
    evaluated_at: datetime
    contributions: tuple[MarketAnalysisPillarContributionV1, ...]
    schema_version: str = "market_analysis_pillar_contribution_collection.v1"

    def __post_init__(self) -> None:
        identity = (_text(self.underlying_symbol, "underlying_symbol").upper(), _text(self.exchange, "exchange").upper())
        if identity not in _IDENTITIES or self.schema_version != "market_analysis_pillar_contribution_collection.v1": raise ValueError("collection identity")
        _aware(self.evaluated_at, "evaluated_at"); _text(self.cycle_id, "cycle_id"); _text(self.observation_id, "observation_id")
        if not isinstance(self.contributions, tuple) or tuple(item.pillar_name for item in self.contributions) != PILLAR_ORDER: raise ValueError("exact ordered contributions")
        if any(type(item) is not MarketAnalysisPillarContributionV1 or (item.cycle_id, item.observation_id, item.underlying_symbol, item.exchange, item.evaluated_at) != (self.cycle_id, self.observation_id, *identity, self.evaluated_at) for item in self.contributions): raise ValueError("collection coherence")
        object.__setattr__(self, "underlying_symbol", identity[0]); object.__setattr__(self, "exchange", identity[1])

    def to_dict(self) -> dict[str, object]:
        return {"cycle_id": self.cycle_id, "observation_id": self.observation_id, "underlying_symbol": self.underlying_symbol, "exchange": self.exchange, "evaluated_at": self.evaluated_at.isoformat(), "contribution_count": len(self.contributions), "contributions": [item.to_dict() for item in self.contributions], "schema_version": self.schema_version}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

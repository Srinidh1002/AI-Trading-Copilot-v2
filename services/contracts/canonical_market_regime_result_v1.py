"""Immutable, paper-only canonical market-regime result contract."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, is_dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from services.core.market_identity import normalize_market_identity

from .broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from .broader_market_regime_component_result_v1 import BroaderMarketRegimeComponentResultV1
from .external_context_regime_component_result_v1 import ExternalContextRegimeComponentResultV1
from .external_market_context_result_v1 import ExternalMarketContextResultV1
from .market_session_validation_v1 import MarketSessionValidationV1
from .technical_intelligence_result_v1 import TechnicalIntelligenceResultV1
from .technical_regime_component_result_v1 import TechnicalRegimeComponentResultV1


_CONTEXT = {"READY", "READY_WITH_WARNINGS", "CONFLICTING", "UNAVAILABLE", "BLOCKED"}
_PRIMARY = {
    "STRONG_BULLISH", "BULLISH", "RANGE_BOUND", "BEARISH", "STRONG_BEARISH",
    "HIGH_VOLATILITY", "EVENT_RISK", "CONFLICTING", "UNAVAILABLE", "BLOCKED",
}
_DIRECTIONAL = {
    "STRONG_BULLISH", "BULLISH", "RANGE_BOUND", "BEARISH", "STRONG_BEARISH",
    "CONFLICTING", "UNAVAILABLE", "BLOCKED",
}
_TREND = {"STRONG_UPTREND", "UPTREND", "SIDEWAYS", "DOWNTREND", "STRONG_DOWNTREND", "CONFLICTING", "UNAVAILABLE"}
_VOLATILITY = {"LOW", "NORMAL", "HIGH", "EXTREME", "UNAVAILABLE"}
_MARKET_CONDITION = {"NORMAL", "HIGH_VOLATILITY", "EVENT_RISK", "SESSION_RESTRICTED", "DATA_QUALITY_RESTRICTED", "CONFLICTING", "UNAVAILABLE", "BLOCKED"}
_CONFIRMATION = {"CONFIRMING", "PARTIAL", "NOT_CONFIRMING", "CONFLICTING", "UNAVAILABLE"}
_SUITABILITY = {"SUITABLE", "CAUTION", "NOT_SUITABLE", "BLOCKED", "UNAVAILABLE"}
_BREADTH = {"POSITIVE", "NEGATIVE", "FLAT", "MIXED", "UNAVAILABLE"}
_EVENT_RISK = {"NONE", "LOW", "MODERATE", "HIGH", "EXTREME", "UNAVAILABLE"}
_RESTRICTION = {"OPEN", "WARNING", "BLOCKED", "SESSION_OWNED", "UNAVAILABLE"}


def _text(value: Any, name: str, uppercase: bool = False) -> str:
    if type(value) is not str or not (normalized := " ".join(value.split())):
        raise ValueError(f"{name} invalid")
    return normalized.upper() if uppercase else normalized


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "to_dict"):
        return _json_safe(value.to_dict())
    if is_dataclass(value):
        return {
            name: _json_safe(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    return value


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class CanonicalMarketRegimeResultV1:
    market_regime_result_id: str
    created_at: datetime
    underlying_symbol: str
    exchange: str
    technical_context: TechnicalIntelligenceResultV1 | None
    broader_market_context: BroaderMarketIntelligenceResultV1 | None
    external_market_context: ExternalMarketContextResultV1 | None
    market_session_validation: MarketSessionValidationV1 | None
    context_status: str
    directional_regime: str
    trend_state: str
    volatility_state: str
    market_condition: str
    confirmation_state: str
    entry_suitability: str
    regime_strength: float
    confidence: float
    available_component_count: int
    unavailable_component_count: int
    confirming_component_count: int
    conflicting_component_count: int
    supporting_evidence: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source_timestamps: Mapping[str, datetime] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "canonical_market_regime_result.v1"
    technical_regime_component: TechnicalRegimeComponentResultV1 | None = None
    broader_market_regime_component: BroaderMarketRegimeComponentResultV1 | None = None
    external_context_regime_component: ExternalContextRegimeComponentResultV1 | None = None
    primary_regime: str | None = None
    breadth_state: str = "UNAVAILABLE"
    event_risk_state: str = "UNAVAILABLE"
    entry_restriction_state: str = "UNAVAILABLE"
    analysis_allowed: bool = False
    new_entries_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "market_regime_result_id", _text(self.market_regime_result_id, "id"))
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at aware")
        identity = normalize_market_identity(self.underlying_symbol, self.exchange)
        if identity is None:
            raise ValueError("identity")
        object.__setattr__(self, "underlying_symbol", identity[0])
        object.__setattr__(self, "exchange", identity[1])

        for name, expected_type in (
            ("technical_context", TechnicalIntelligenceResultV1),
            ("broader_market_context", BroaderMarketIntelligenceResultV1),
            ("external_market_context", ExternalMarketContextResultV1),
        ):
            child = getattr(self, name)
            if child is not None and (type(child) is not expected_type or (child.underlying_symbol, child.exchange) != identity):
                raise TypeError(f"{name} mismatch")
        if self.market_session_validation is not None:
            session = self.market_session_validation
            if type(session) is not MarketSessionValidationV1:
                raise TypeError("market_session_validation")
            if (session.symbol, session.exchange) != identity:
                raise ValueError("market_session_validation identity mismatch")
        for name, expected_type in (
            ("technical_regime_component", TechnicalRegimeComponentResultV1),
            ("broader_market_regime_component", BroaderMarketRegimeComponentResultV1),
            ("external_context_regime_component", ExternalContextRegimeComponentResultV1),
        ):
            child = getattr(self, name)
            if child is None:
                continue
            if type(child) is not expected_type:
                raise TypeError(name)
            if (child.underlying_symbol, child.exchange) != identity:
                raise ValueError(f"{name} identity mismatch")

        for name, vocabulary in (
            ("context_status", _CONTEXT),
            ("directional_regime", _DIRECTIONAL),
            ("trend_state", _TREND),
            ("volatility_state", _VOLATILITY),
            ("market_condition", _MARKET_CONDITION),
            ("confirmation_state", _CONFIRMATION),
            ("entry_suitability", _SUITABILITY),
            ("breadth_state", _BREADTH),
            ("event_risk_state", _EVENT_RISK),
            ("entry_restriction_state", _RESTRICTION),
        ):
            value = _text(getattr(self, name), name, uppercase=True)
            if value not in vocabulary:
                raise ValueError("vocabulary")
            object.__setattr__(self, name, value)
        primary = self.directional_regime if self.primary_regime is None else _text(self.primary_regime, "primary_regime", uppercase=True)
        if primary not in _PRIMARY:
            raise ValueError("primary_regime")
        object.__setattr__(self, "primary_regime", primary)

        for name in ("regime_strength", "confidence"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0 <= float(value) <= 1:
                raise ValueError(name)
            object.__setattr__(self, name, float(value))
        for name in (
            "available_component_count", "unavailable_component_count",
            "confirming_component_count", "conflicting_component_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError("counts")
        if self.available_component_count + self.unavailable_component_count != 4:
            raise ValueError("counts")
        if type(self.analysis_allowed) is not bool or type(self.new_entries_allowed) is not bool:
            raise ValueError("flags")
        if not self.analysis_allowed and self.new_entries_allowed:
            raise ValueError("analysis/entry consistency")
        if self.entry_restriction_state == "BLOCKED" and self.new_entries_allowed:
            raise ValueError("blocked restriction")
        if self.entry_restriction_state == "OPEN" and not self.new_entries_allowed:
            raise ValueError("open restriction")

        for name in ("supporting_evidence", "contradictions", "blockers", "warnings"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise TypeError(name)
            object.__setattr__(self, name, tuple(sorted(set(_text(item, name, uppercase=True) for item in value))))
        if not isinstance(self.source_timestamps, Mapping):
            raise TypeError("source_timestamps")
        timestamps: dict[str, datetime] = {}
        for key, value in self.source_timestamps.items():
            normalized_key = _text(key, "source", uppercase=True)
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError("timestamps")
            timestamps[normalized_key] = value
        object.__setattr__(self, "source_timestamps", MappingProxyType(dict(sorted(timestamps.items()))))
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata")
        safe_metadata = json.loads(json.dumps(dict(self.metadata), sort_keys=True, allow_nan=False))
        object.__setattr__(self, "metadata", _freeze_json(safe_metadata))

        blocked = self.primary_regime == "BLOCKED" or self.context_status == "BLOCKED"
        conflicting = self.primary_regime == "CONFLICTING" or self.context_status == "CONFLICTING"
        unavailable = self.primary_regime == "UNAVAILABLE" or self.context_status == "UNAVAILABLE"
        if blocked and (not self.blockers or self.entry_suitability != "BLOCKED" or self.new_entries_allowed):
            raise ValueError("blocked coherence")
        if conflicting and not self.contradictions:
            raise ValueError("conflicting coherence")
        if unavailable:
            if self.regime_strength != 0.0 or self.entry_suitability not in {"UNAVAILABLE", "BLOCKED"}:
                raise ValueError("unavailable coherence")
            if self.context_status == "UNAVAILABLE" and any(
                value != "UNAVAILABLE"
                for value in (self.trend_state, self.volatility_state, self.breadth_state, self.confirmation_state)
            ):
                raise ValueError("unavailable dimensions")
        if self.context_status == "READY":
            if self.warnings or self.blockers or self.contradictions or self.primary_regime in {"UNAVAILABLE", "CONFLICTING", "BLOCKED"}:
                raise ValueError("ready coherence")
        if self.context_status == "READY_WITH_WARNINGS" and (not self.warnings or self.blockers or self.contradictions):
            raise ValueError("ready warning coherence")
        if self.primary_regime == "EVENT_RISK":
            if self.event_risk_state not in {"HIGH", "EXTREME"}:
                raise ValueError("event risk coherence")
            if self.entry_restriction_state != "OPEN" and self.entry_suitability == "SUITABLE":
                raise ValueError("event restriction coherence")
        if self.primary_regime == "HIGH_VOLATILITY" and self.volatility_state not in {"HIGH", "EXTREME"}:
            raise ValueError("volatility coherence")
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.schema_version != "canonical_market_regime_result.v1":
            raise ValueError("paper")

    @property
    def canonical_market_regime_result_id(self) -> str:
        """Compatibility name for the established result identifier."""
        return self.market_regime_result_id

    def to_dict(self) -> dict[str, Any]:
        result = {name: _json_safe(getattr(self, name)) for name in self.__dataclass_fields__}
        result["created_at"] = self.created_at.isoformat()
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        result.pop("market_regime_result_id")
        result.pop("created_at")
        return result

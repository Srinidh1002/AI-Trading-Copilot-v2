"""Pure adapters for already-produced technical, timeframe, and regime evidence."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
from services.contracts.market_analysis_candidate_v1 import MarketAnalysisEvidenceV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.multi_timeframe_snapshot_v1 import MultiTimeframeSnapshotV1
from services.contracts.technical_intelligence_result_v1 import TechnicalIntelligenceResultV1
from services.contracts.timeframe_evidence_v1 import TimeframeEvidenceV1
from services.contracts.timeframe_technical_evidence_v1 import TimeframeTechnicalEvidenceV1


_IDENTITIES = {("NIFTY", "NSE"), ("SENSEX", "BSE")}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _finite(value: object, name: str, minimum: float, maximum: float) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError(name)
    return float(value)


def _freeze(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        frozen = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(name)
            frozen[key] = _freeze(item, name)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item, name) for item in value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(name)
        return value
    if isinstance(value, datetime):
        return _aware(value, name)
    raise ValueError(name)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(name)
    return _freeze(value, name)


def _normalise_identity(symbol: object, exchange: object) -> tuple[str, str]:
    identity = (_text(symbol, "underlying_symbol").upper(), _text(exchange, "exchange").upper())
    if identity not in _IDENTITIES:
        raise ValueError("unsupported market identity")
    return identity


def _technical_ready(value: TechnicalIntelligenceResultV1) -> bool:
    return (
        value.status in {"READY", "READY_WITH_WARNINGS"}
        and bool(value.timeframe_evidence)
        and not value.blockers
    )


def _session_ready(value: MarketSessionValidationV1) -> bool:
    return (
        value.session_state == "REGULAR"
        and value.analysis_allowed
        and value.paper_preparation_allowed
        and not value.stale
        and not value.future_timestamp
        and not value.blockers
        and not value.errors
    )


def _broader_ready(value: BroaderMarketIntelligenceResultV1) -> bool:
    return (
        value.intelligence_status in {"READY", "READY_WITH_WARNINGS"}
        and value.aggregate_bias not in {"UNAVAILABLE", "CONFLICTING"}
        and not value.blockers
        and not value.contradictions
    )


def _external_ready(value: ExternalMarketContextResultV1) -> bool:
    return (
        value.context_status in {"READY", "READY_WITH_WARNINGS"}
        and value.aggregate_direction not in {"UNAVAILABLE", "CONFLICTING"}
        and value.entry_restriction_state in {"OPEN", "WARNING"}
        and value.analysis_allowed
        and value.new_entries_allowed
        and not value.blockers
        and not value.contradictions
    )


def _tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


def _identity(value: object, symbol: str, exchange: str) -> None:
    child_symbol = getattr(value, "underlying_symbol", getattr(value, "symbol", None))
    if (child_symbol, getattr(value, "exchange", None)) != (symbol, exchange):
        raise ValueError("identity mismatch")


@dataclass(frozen=True, slots=True)
class TechnicalEvidenceAdapterInputV1:
    technical_intelligence_result_id: str
    created_at: datetime
    multi_timeframe_snapshot_id: str
    multi_timeframe_quality_result_id: str
    underlying_symbol: str
    exchange: str
    timeframe_evidence: tuple[TimeframeTechnicalEvidenceV1, ...]
    status: str
    aggregate_bias: str
    aggregate_strength: float
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    required_timeframes: tuple[str, ...] = ()
    bullish_timeframes: tuple[str, ...] = ()
    bearish_timeframes: tuple[str, ...] = ()
    neutral_timeframes: tuple[str, ...] = ()
    unavailable_timeframes: tuple[str, ...] = ()
    aligned_timeframes: tuple[str, ...] = ()
    conflicting_timeframes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        symbol, exchange = _normalise_identity(self.underlying_symbol, self.exchange)
        object.__setattr__(self, "underlying_symbol", symbol)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "technical_intelligence_result_id", _text(self.technical_intelligence_result_id, "technical_intelligence_result_id"))
        object.__setattr__(self, "multi_timeframe_snapshot_id", _text(self.multi_timeframe_snapshot_id, "multi_timeframe_snapshot_id"))
        object.__setattr__(self, "multi_timeframe_quality_result_id", _text(self.multi_timeframe_quality_result_id, "multi_timeframe_quality_result_id"))
        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        if not isinstance(self.timeframe_evidence, tuple):
            raise TypeError("timeframe_evidence")
        object.__setattr__(self, "status", _text(self.status, "status").upper())
        object.__setattr__(self, "aggregate_bias", _text(self.aggregate_bias, "aggregate_bias").upper())
        object.__setattr__(self, "aggregate_strength", _finite(self.aggregate_strength, "aggregate_strength", 0.0, 1.0))
        for name in ("blockers", "warnings", "required_timeframes", "bullish_timeframes", "bearish_timeframes", "neutral_timeframes", "unavailable_timeframes", "aligned_timeframes", "conflicting_timeframes"):
            object.__setattr__(self, name, _tuple(getattr(self, name), name))


def adapt_technical_intelligence(value: TechnicalEvidenceAdapterInputV1) -> TechnicalIntelligenceResultV1:
    if type(value) is not TechnicalEvidenceAdapterInputV1 or not value.timeframe_evidence:
        raise ValueError("technical evidence required")
    for item in value.timeframe_evidence:
        if type(item) is not TimeframeTechnicalEvidenceV1:
            raise TypeError("timeframe technical evidence")
        _identity(item, value.underlying_symbol, value.exchange)
    names = tuple(item.timeframe for item in value.timeframe_evidence)
    if len(names) != len(set(names)):
        raise ValueError("duplicate technical timeframe")
    if value.required_timeframes and names != value.required_timeframes:
        raise ValueError("technical timeframe order")
    nonready = any(item.blockers or not item.indicators for item in value.timeframe_evidence)
    if value.status in {"READY", "READY_WITH_WARNINGS"} and nonready:
        raise ValueError("non-ready technical evidence requires explicit status")
    return TechnicalIntelligenceResultV1(
        value.technical_intelligence_result_id, value.created_at,
        value.multi_timeframe_snapshot_id, value.multi_timeframe_quality_result_id,
        value.underlying_symbol, value.exchange, value.timeframe_evidence,
        value.status, value.aggregate_bias, value.aggregate_strength,
        blockers=_tuple(value.blockers, "blockers"), warnings=_tuple(value.warnings, "warnings"),
        required_timeframes=value.required_timeframes,
        bullish_timeframes=value.bullish_timeframes, bearish_timeframes=value.bearish_timeframes,
        neutral_timeframes=value.neutral_timeframes, unavailable_timeframes=value.unavailable_timeframes,
        aligned_timeframes=value.aligned_timeframes, conflicting_timeframes=value.conflicting_timeframes,
    )


@dataclass(frozen=True, slots=True)
class MultiTimeframeAdapterInputV1:
    multi_timeframe_snapshot_id: str
    created_at: datetime
    underlying_symbol: str
    exchange: str
    required_timeframes: tuple[str, ...]
    timeframe_evidence: tuple[TimeframeEvidenceV1, ...]
    primary_timeframe: str
    synchronization_reference_at: datetime | None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        symbol, exchange = _normalise_identity(self.underlying_symbol, self.exchange)
        object.__setattr__(self, "underlying_symbol", symbol)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "multi_timeframe_snapshot_id", _text(self.multi_timeframe_snapshot_id, "multi_timeframe_snapshot_id"))
        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        object.__setattr__(self, "required_timeframes", _tuple(self.required_timeframes, "required_timeframes"))
        if not self.required_timeframes:
            raise ValueError("required timeframes required")
        if len(self.required_timeframes) != len(set(self.required_timeframes)):
            raise ValueError("duplicate required timeframe")
        if not isinstance(self.timeframe_evidence, tuple):
            raise TypeError("timeframe_evidence")
        object.__setattr__(self, "primary_timeframe", _text(self.primary_timeframe, "primary_timeframe"))
        if self.primary_timeframe not in self.required_timeframes:
            raise ValueError("primary timeframe")
        if self.synchronization_reference_at is not None:
            object.__setattr__(self, "synchronization_reference_at", _aware(self.synchronization_reference_at, "synchronization_reference_at"))
        object.__setattr__(self, "blockers", _tuple(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _tuple(self.warnings, "warnings"))


def adapt_multi_timeframe_snapshot(value: MultiTimeframeAdapterInputV1) -> MultiTimeframeSnapshotV1:
    if type(value) is not MultiTimeframeAdapterInputV1 or not value.timeframe_evidence:
        raise ValueError("timeframe evidence required")
    names = tuple(item.timeframe for item in value.timeframe_evidence)
    if len(names) != len(set(names)):
        raise ValueError("duplicate timeframe")
    if names != value.required_timeframes:
        raise ValueError("requested timeframe order")
    for item in value.timeframe_evidence:
        if type(item) is not TimeframeEvidenceV1:
            raise TypeError("timeframe evidence")
        _identity(item, value.underlying_symbol, value.exchange)
    explicit = list(_tuple(value.blockers, "blockers"))
    for item in value.timeframe_evidence:
        if item.quality_status != "VALID" or not item.history_sufficient or not item.latest_candle_complete:
            explicit.append(f"TIMEFRAME_NOT_READY_{item.timeframe}")
    return MultiTimeframeSnapshotV1(value.multi_timeframe_snapshot_id, value.created_at, value.underlying_symbol, value.exchange, value.required_timeframes, value.timeframe_evidence, value.primary_timeframe, value.synchronization_reference_at, blockers=tuple(dict.fromkeys(explicit)), warnings=_tuple(value.warnings, "warnings"))


@dataclass(frozen=True, slots=True)
class RegimeEvidenceAdapterInputV1:
    market_regime_result_id: str
    created_at: datetime
    underlying_symbol: str
    exchange: str
    technical_context: TechnicalIntelligenceResultV1 | None
    market_session_validation: MarketSessionValidationV1 | None
    broader_market_context: BroaderMarketIntelligenceResultV1 | None
    external_market_context: ExternalMarketContextResultV1 | None
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
    source_timestamps: Mapping[str, datetime] = None
    metadata: Mapping[str, Any] = None
    primary_regime: str | None = None
    breadth_state: str = "UNAVAILABLE"
    event_risk_state: str = "UNAVAILABLE"
    entry_restriction_state: str = "UNAVAILABLE"
    analysis_allowed: bool = False
    new_entries_allowed: bool = False

    def __post_init__(self) -> None:
        symbol, exchange = _normalise_identity(self.underlying_symbol, self.exchange)
        object.__setattr__(self, "underlying_symbol", symbol)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "market_regime_result_id", _text(self.market_regime_result_id, "market_regime_result_id"))
        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        for name in ("context_status", "directional_regime", "trend_state", "volatility_state", "market_condition", "confirmation_state", "entry_suitability", "breadth_state", "event_risk_state", "entry_restriction_state"):
            object.__setattr__(self, name, _text(getattr(self, name), name).upper())
        if self.primary_regime is not None:
            object.__setattr__(self, "primary_regime", _text(self.primary_regime, "primary_regime").upper())
        object.__setattr__(self, "regime_strength", _finite(self.regime_strength, "regime_strength", 0.0, 1.0))
        object.__setattr__(self, "confidence", _finite(self.confidence, "confidence", 0.0, 1.0))
        for name in ("available_component_count", "unavailable_component_count", "confirming_component_count", "conflicting_component_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(name)
        for name in ("supporting_evidence", "contradictions", "blockers", "warnings"):
            object.__setattr__(self, name, _tuple(getattr(self, name), name))
        object.__setattr__(self, "source_timestamps", _mapping({} if self.source_timestamps is None else self.source_timestamps, "source_timestamps"))
        object.__setattr__(self, "metadata", _mapping({} if self.metadata is None else self.metadata, "metadata"))


def adapt_canonical_market_regime(
    value: RegimeEvidenceAdapterInputV1,
) -> CanonicalMarketRegimeResultV1:
    if type(value) is not RegimeEvidenceAdapterInputV1:
        raise TypeError("regime adapter input")

    for item in (
        value.technical_context,
        value.market_session_validation,
        value.broader_market_context,
        value.external_market_context,
    ):
        if item is not None:
            _identity(item, value.underlying_symbol, value.exchange)

    blockers = value.blockers
    contradictions = value.contradictions
    warnings = value.warnings

    mandatory_missing = (
        value.technical_context is None
        or value.market_session_validation is None
    )
    mandatory_blocked = (
        value.market_session_validation is not None
        and not _session_ready(value.market_session_validation)
    )
    technical_nonready = (
        value.technical_context is not None
        and not _technical_ready(value.technical_context)
    )
    broader_nonready = (
        value.broader_market_context is not None
        and not _broader_ready(value.broader_market_context)
    )
    external_nonready = (
        value.external_market_context is not None
        and not _external_ready(value.external_market_context)
    )
    supplied_conflict = bool(contradictions) or any(
        (
            value.technical_context is not None
            and value.technical_context.status == "CONFLICTING",
            value.broader_market_context is not None
            and value.broader_market_context.intelligence_status == "CONFLICTING",
            value.external_market_context is not None
            and value.external_market_context.context_status == "CONFLICTING",
        )
    )

    if mandatory_blocked:
        blockers = tuple(dict.fromkeys(blockers + ("SESSION_BLOCKED",)))
        fields = (
            "BLOCKED", "BLOCKED", "UNAVAILABLE", "UNAVAILABLE",
            "SESSION_RESTRICTED", "UNAVAILABLE", "BLOCKED",
            0.0, 0.0, 0, 4, 0, 0,
            "BLOCKED", "UNAVAILABLE", "UNAVAILABLE", "BLOCKED",
            False, False,
        )
    elif mandatory_missing:
        blockers = tuple(
            dict.fromkeys(
                blockers + ("MANDATORY_REGIME_COMPONENT_UNAVAILABLE",)
            )
        )
        fields = (
            "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE",
            "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE",
            0.0, 0.0, 0, 4, 0, 0,
            "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE",
            False, False,
        )
    elif supplied_conflict:
        contradictions = contradictions or (
            "SUPPLIED_REGIME_COMPONENT_CONFLICT",
        )
        fields = (
            "CONFLICTING", "CONFLICTING", "CONFLICTING", "UNAVAILABLE",
            "CONFLICTING", "CONFLICTING", "CAUTION",
            0.0, 0.0, 0, 4, 0, 1,
            "CONFLICTING", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE",
            False, False,
        )
    elif technical_nonready or broader_nonready or external_nonready:
        failures = []
        if technical_nonready:
            failures.append("TECHNICAL_CONTEXT_UNAVAILABLE")
        if broader_nonready:
            failures.append("BROADER_MARKET_CONTEXT_UNAVAILABLE")
        if external_nonready:
            failures.append("EXTERNAL_MARKET_CONTEXT_UNAVAILABLE")
        blockers = tuple(dict.fromkeys(blockers + tuple(failures)))
        fields = (
            "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE",
            "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE",
            0.0, 0.0, 0, 4, 0, 0,
            "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE",
            False, False,
        )
    else:
        if value.context_status == "READY" and (
            not value.analysis_allowed or not value.new_entries_allowed
        ):
            raise ValueError("READY regime cannot disable analysis or entries")
        fields = (
            value.context_status,
            value.directional_regime,
            value.trend_state,
            value.volatility_state,
            value.market_condition,
            value.confirmation_state,
            value.entry_suitability,
            value.regime_strength,
            value.confidence,
            value.available_component_count,
            value.unavailable_component_count,
            value.confirming_component_count,
            value.conflicting_component_count,
            value.primary_regime,
            value.breadth_state,
            value.event_risk_state,
            value.entry_restriction_state,
            value.analysis_allowed,
            value.new_entries_allowed,
        )

    return CanonicalMarketRegimeResultV1(
        value.market_regime_result_id,
        value.created_at,
        value.underlying_symbol,
        value.exchange,
        value.technical_context,
        value.broader_market_context,
        value.external_market_context,
        value.market_session_validation,
        *fields[:13],
        supporting_evidence=value.supporting_evidence,
        contradictions=contradictions,
        blockers=blockers,
        warnings=warnings,
        source_timestamps=value.source_timestamps,
        metadata=value.metadata,
        primary_regime=fields[13],
        breadth_state=fields[14],
        event_risk_state=fields[15],
        entry_restriction_state=fields[16],
        analysis_allowed=fields[17],
        new_entries_allowed=fields[18],
    )


def adapt_technical_pillar_evidence(status: str, source_ids: tuple[str, ...], provenance: Mapping[str, Any], summary: Mapping[str, Any]) -> MarketAnalysisEvidenceV1:
    """Retain one supplied technical pillar without inventing analytical values."""
    return MarketAnalysisEvidenceV1(status=status, source_ids=source_ids, provenance=provenance, summary=summary)

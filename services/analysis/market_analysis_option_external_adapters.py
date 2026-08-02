"""Pure supplied-evidence adapters for Task 2B Slice 4.

This module performs no provider access, calculation, ranking, composition,
or execution. It validates and retains already-produced option, broader-market,
and external-context evidence for one NIFTY or SENSEX PAPER analysis.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType
from typing import Any, Mapping

from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.cross_market_evidence_v1 import CrossMarketEvidenceV1
from services.contracts.event_risk_context_result_v1 import EventRiskContextResultV1
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
from services.contracts.global_market_context_result_v1 import GlobalMarketContextResultV1
from services.contracts.institutional_flow_context_result_v1 import InstitutionalFlowContextResultV1
from services.contracts.market_analysis_candidate_v1 import MarketAnalysisEvidenceV1
from services.contracts.market_breadth_evidence_v1 import MarketBreadthEvidenceV1
from services.contracts.option_chain_intelligence_result_v1 import OptionChainIntelligenceResultV1
from services.contracts.option_chain_metric_v1 import OptionChainMetricV1
from services.contracts.option_contract_candidate_v1 import OptionContractCandidateV1
from services.contracts.option_contract_ranking_result_v1 import OptionContractRankingResultV1
from services.contracts.volatility_context_v1 import VolatilityContextV1

_IDENTITIES = {("NIFTY", "NSE"), ("SENSEX", "BSE")}
_READY = {"READY", "READY_WITH_WARNINGS"}


def _text(value: object, name: str, *, upper: bool = False) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned.upper() if upper else cleaned


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


def _finite(value: object, name: str, minimum: float, maximum: float) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise TypeError(name)
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(name)
    return result


def _freeze(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(name)
            output[key] = _freeze(item, name)
        return MappingProxyType(output)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item, name) for item in value)
    if value is None or isinstance(value, (str, bool, int, date)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(name)
        return value
    raise ValueError(name)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(name)
    return _freeze(value, name)


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _identity(symbol: object, exchange: object) -> tuple[str, str]:
    result = (_text(symbol, "underlying_symbol", upper=True), _text(exchange, "exchange", upper=True))
    if result not in _IDENTITIES:
        raise ValueError("unsupported market identity")
    return result


def _child_identity(value: object, expected: tuple[str, str], name: str) -> None:
    symbol = getattr(value, "underlying_symbol", getattr(value, "primary_symbol", None))
    exchange = getattr(value, "exchange", getattr(value, "primary_exchange", None))
    if (symbol, exchange) != expected:
        raise ValueError(f"{name} identity mismatch")


@dataclass(frozen=True, slots=True)
class OptionChainEvidenceAdapterInputV1:
    option_chain_intelligence_result_id: str
    created_at: datetime
    option_chain_snapshot_id: str
    option_chain_quality_result_id: str
    underlying_symbol: str
    exchange: str
    expiry: date
    metrics: tuple[OptionChainMetricV1, ...]
    intelligence_status: str
    aggregate_bias: str
    aggregate_strength: float
    bullish_metrics: tuple[str, ...]
    bearish_metrics: tuple[str, ...]
    neutral_metrics: tuple[str, ...]
    unavailable_metrics: tuple[str, ...]
    valid_metric_count: int
    unavailable_metric_count: int
    support_strikes: tuple[float, ...] = ()
    resistance_strikes: tuple[float, ...] = ()
    max_pain_strike: float | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    source_status: str = "AVAILABLE"

    def __post_init__(self) -> None:
        symbol, exchange = _identity(self.underlying_symbol, self.exchange)
        object.__setattr__(self, "underlying_symbol", symbol)
        object.__setattr__(self, "exchange", exchange)
        for name in ("option_chain_intelligence_result_id", "option_chain_snapshot_id", "option_chain_quality_result_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        if isinstance(self.expiry, datetime) or not isinstance(self.expiry, date):
            raise TypeError("expiry")
        if not isinstance(self.metrics, tuple):
            raise TypeError("metrics")
        if len({metric.metric_name for metric in self.metrics}) != len(self.metrics):
            raise ValueError("duplicate option-chain metric")
        for metric in self.metrics:
            if type(metric) is not OptionChainMetricV1:
                raise TypeError("metrics")
        for name in ("bullish_metrics", "bearish_metrics", "neutral_metrics", "unavailable_metrics", "blockers", "warnings", "reasons"):
            object.__setattr__(self, name, _messages(getattr(self, name), name))
        object.__setattr__(self, "intelligence_status", _text(self.intelligence_status, "intelligence_status", upper=True))
        object.__setattr__(self, "aggregate_bias", _text(self.aggregate_bias, "aggregate_bias", upper=True))
        object.__setattr__(self, "source_status", _text(self.source_status, "source_status", upper=True))
        object.__setattr__(self, "aggregate_strength", _finite(self.aggregate_strength, "aggregate_strength", 0.0, 1.0))
        for name in ("valid_metric_count", "unavailable_metric_count"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(name)


def adapt_option_chain_intelligence(value: OptionChainEvidenceAdapterInputV1) -> OptionChainIntelligenceResultV1:
    if type(value) is not OptionChainEvidenceAdapterInputV1:
        raise TypeError("option-chain adapter input")
    if value.intelligence_status in _READY and not value.metrics:
        raise ValueError("READY option-chain evidence requires metrics")
    return OptionChainIntelligenceResultV1(
        option_chain_intelligence_result_id=value.option_chain_intelligence_result_id,
        created_at=value.created_at,
        option_chain_snapshot_id=value.option_chain_snapshot_id,
        option_chain_quality_result_id=value.option_chain_quality_result_id,
        underlying_symbol=value.underlying_symbol,
        exchange=value.exchange,
        expiry=value.expiry,
        metrics=value.metrics,
        intelligence_status=value.intelligence_status,
        aggregate_bias=value.aggregate_bias,
        aggregate_strength=value.aggregate_strength,
        bullish_metrics=value.bullish_metrics,
        bearish_metrics=value.bearish_metrics,
        neutral_metrics=value.neutral_metrics,
        unavailable_metrics=value.unavailable_metrics,
        valid_metric_count=value.valid_metric_count,
        unavailable_metric_count=value.unavailable_metric_count,
        support_strikes=value.support_strikes,
        resistance_strikes=value.resistance_strikes,
        max_pain_strike=value.max_pain_strike,
        blockers=value.blockers,
        warnings=value.warnings,
        reasons=value.reasons,
        source_status=value.source_status,
    )


@dataclass(frozen=True, slots=True)
class OptionContractRankingAdapterInputV1:
    ranking_id: str
    ranked_at: datetime
    universe_id: str | None
    intelligence_result_id: str | None
    underlying_symbol: str
    exchange: str
    directional_bias: str
    required_option_type: str | None
    ranking_status: str
    ranked_candidates: tuple[OptionContractCandidateV1, ...]
    rejected_candidates: tuple[OptionContractCandidateV1, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        symbol, exchange = _identity(self.underlying_symbol, self.exchange)
        object.__setattr__(self, "underlying_symbol", symbol)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "ranking_id", _text(self.ranking_id, "ranking_id"))
        object.__setattr__(self, "ranked_at", _aware(self.ranked_at, "ranked_at"))
        for name in ("universe_id", "intelligence_result_id", "required_option_type"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, _text(getattr(self, name), name, upper=name == "required_option_type"))
        object.__setattr__(self, "directional_bias", _text(self.directional_bias, "directional_bias", upper=True))
        object.__setattr__(self, "ranking_status", _text(self.ranking_status, "ranking_status", upper=True))
        for name in ("ranked_candidates", "rejected_candidates"):
            items = getattr(self, name)
            if not isinstance(items, tuple) or not all(type(item) is OptionContractCandidateV1 for item in items):
                raise TypeError(name)
            for item in items:
                _child_identity(item.contract, (symbol, exchange), name)
        contract_ids = [item.contract.contract_id for item in self.ranked_candidates + self.rejected_candidates]
        if len(contract_ids) != len(set(contract_ids)):
            raise ValueError("duplicate ranked option contract")
        for name in ("blockers", "warnings", "diagnostics"):
            object.__setattr__(self, name, _messages(getattr(self, name), name))
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))


def adapt_option_contract_ranking(value: OptionContractRankingAdapterInputV1) -> OptionContractRankingResultV1:
    if type(value) is not OptionContractRankingAdapterInputV1:
        raise TypeError("option ranking adapter input")
    if value.ranking_status == "RANKED" and not value.ranked_candidates:
        raise ValueError("RANKED result requires ranked candidates")
    return OptionContractRankingResultV1(
        value.ranking_id, value.ranked_at, value.universe_id,
        value.intelligence_result_id, value.underlying_symbol, value.exchange,
        value.directional_bias, value.required_option_type,
        value.ranking_status, value.ranked_candidates,
        value.rejected_candidates, blockers=value.blockers,
        warnings=value.warnings, diagnostics=value.diagnostics,
        metadata=_thaw(value.metadata),
    )


@dataclass(frozen=True, slots=True)
class BroaderMarketEvidenceAdapterInputV1:
    broader_market_intelligence_result_id: str
    created_at: datetime
    underlying_symbol: str
    exchange: str
    cross_market_evidence: tuple[CrossMarketEvidenceV1, ...]
    breadth_evidence: MarketBreadthEvidenceV1 | None
    volatility_context: VolatilityContextV1 | None
    intelligence_status: str
    aggregate_bias: str
    aggregate_strength: float
    confirmation_state: str
    divergence_state: str
    supporting_evidence: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source_timestamps: Mapping[str, datetime] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        symbol, exchange = _identity(self.underlying_symbol, self.exchange)
        object.__setattr__(self, "underlying_symbol", symbol)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "broader_market_intelligence_result_id", _text(self.broader_market_intelligence_result_id, "broader_market_intelligence_result_id"))
        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        if not isinstance(self.cross_market_evidence, tuple):
            raise TypeError("cross_market_evidence")
        for item in self.cross_market_evidence:
            if type(item) is not CrossMarketEvidenceV1:
                raise TypeError("cross_market_evidence")
            _child_identity(item, (symbol, exchange), "cross_market_evidence")
        for name, kind in (("breadth_evidence", MarketBreadthEvidenceV1), ("volatility_context", VolatilityContextV1)):
            item = getattr(self, name)
            if item is not None:
                if type(item) is not kind:
                    raise TypeError(name)
                _child_identity(item, (symbol, exchange), name)
        for name in ("intelligence_status", "aggregate_bias", "confirmation_state", "divergence_state"):
            object.__setattr__(self, name, _text(getattr(self, name), name, upper=True))
        object.__setattr__(self, "aggregate_strength", _finite(self.aggregate_strength, "aggregate_strength", 0.0, 1.0))
        for name in ("supporting_evidence", "contradictions", "blockers", "warnings"):
            object.__setattr__(self, name, _messages(getattr(self, name), name))
        object.__setattr__(self, "source_timestamps", _mapping(self.source_timestamps, "source_timestamps"))
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))


def adapt_broader_market_intelligence(value: BroaderMarketEvidenceAdapterInputV1) -> BroaderMarketIntelligenceResultV1:
    if type(value) is not BroaderMarketEvidenceAdapterInputV1:
        raise TypeError("broader-market adapter input")
    available = sum(item.evidence_status in _READY for item in value.cross_market_evidence)
    available += bool(value.breadth_evidence is not None and value.breadth_evidence.evidence_status in _READY)
    available += bool(value.volatility_context is not None and value.volatility_context.context_status in _READY)
    total = len(value.cross_market_evidence) + int(value.breadth_evidence is not None) + int(value.volatility_context is not None)
    if value.intelligence_status in _READY and not available:
        raise ValueError("READY broader-market evidence requires an available component")
    return BroaderMarketIntelligenceResultV1(
        value.broader_market_intelligence_result_id, value.created_at,
        value.underlying_symbol, value.exchange, value.cross_market_evidence,
        value.breadth_evidence, value.volatility_context,
        value.intelligence_status, value.aggregate_bias,
        value.aggregate_strength, value.confirmation_state,
        value.divergence_state, available, total - available,
        supporting_evidence=value.supporting_evidence,
        contradictions=value.contradictions, blockers=value.blockers,
        warnings=value.warnings, source_timestamps=_thaw(value.source_timestamps),
        metadata=_thaw(value.metadata),
    )


@dataclass(frozen=True, slots=True)
class ExternalContextEvidenceAdapterInputV1:
    external_market_context_result_id: str
    created_at: datetime
    underlying_symbol: str
    exchange: str
    global_context: GlobalMarketContextResultV1 | None
    institutional_context: InstitutionalFlowContextResultV1 | None
    event_context: EventRiskContextResultV1 | None
    context_status: str
    aggregate_direction: str
    aggregate_strength: float
    confirmation_state: str
    risk_level: str
    entry_restriction_state: str
    analysis_allowed: bool
    new_entries_allowed: bool
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

    def __post_init__(self) -> None:
        symbol, exchange = _identity(self.underlying_symbol, self.exchange)
        object.__setattr__(self, "underlying_symbol", symbol)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "external_market_context_result_id", _text(self.external_market_context_result_id, "external_market_context_result_id"))
        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        for name, kind in (("global_context", GlobalMarketContextResultV1), ("institutional_context", InstitutionalFlowContextResultV1), ("event_context", EventRiskContextResultV1)):
            item = getattr(self, name)
            if item is not None:
                if type(item) is not kind:
                    raise TypeError(name)
                _child_identity(item, (symbol, exchange), name)
        for name in ("context_status", "aggregate_direction", "confirmation_state", "risk_level", "entry_restriction_state"):
            object.__setattr__(self, name, _text(getattr(self, name), name, upper=True))
        object.__setattr__(self, "aggregate_strength", _finite(self.aggregate_strength, "aggregate_strength", 0.0, 1.0))
        if type(self.analysis_allowed) is not bool or type(self.new_entries_allowed) is not bool:
            raise TypeError("analysis and entry permissions")
        for name in ("available_component_count", "unavailable_component_count", "confirming_component_count", "conflicting_component_count"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(name)
        if self.available_component_count + self.unavailable_component_count != 3:
            raise ValueError("external component counts")
        for name in ("supporting_evidence", "contradictions", "blockers", "warnings"):
            object.__setattr__(self, name, _messages(getattr(self, name), name))
        object.__setattr__(self, "source_timestamps", _mapping(self.source_timestamps, "source_timestamps"))
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))


def adapt_external_market_context(value: ExternalContextEvidenceAdapterInputV1) -> ExternalMarketContextResultV1:
    if type(value) is not ExternalContextEvidenceAdapterInputV1:
        raise TypeError("external-context adapter input")
    available = value.available_component_count
    unavailable = value.unavailable_component_count
    confirming = value.confirming_component_count
    conflicting = value.conflicting_component_count
    if value.context_status == "READY" and (not value.analysis_allowed or not value.new_entries_allowed):
        raise ValueError("READY external context cannot disable analysis or entries")
    if value.context_status in {"BLOCKED", "UNAVAILABLE", "CONFLICTING"} and (value.analysis_allowed or value.new_entries_allowed):
        raise ValueError("non-ready external context must fail closed")
    return ExternalMarketContextResultV1(
        value.external_market_context_result_id, value.created_at,
        value.underlying_symbol, value.exchange, value.global_context,
        value.institutional_context, value.event_context, value.context_status,
        value.aggregate_direction, value.aggregate_strength,
        value.confirmation_state, value.risk_level,
        value.entry_restriction_state, value.analysis_allowed,
        value.new_entries_allowed, available, unavailable, confirming,
        conflicting, supporting_evidence=value.supporting_evidence,
        contradictions=value.contradictions, blockers=value.blockers,
        warnings=value.warnings, source_timestamps=_thaw(value.source_timestamps),
        metadata=_thaw(value.metadata),
    )


def adapt_option_external_pillar_evidence(
    status: str,
    source_ids: tuple[str, ...],
    provenance: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> MarketAnalysisEvidenceV1:
    """Retain supplied OI/PCR/IV/Greeks/premium/liquidity evidence unchanged."""
    return MarketAnalysisEvidenceV1(
        status=status,
        source_ids=source_ids,
        provenance=provenance,
        summary=summary,
    )

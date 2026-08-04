"""Immutable, supplied-evidence-only candidate for one PAPER market analysis."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from .broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from .canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
from .external_market_context_result_v1 import ExternalMarketContextResultV1
from .market_data_quality_result_v1 import MarketDataQualityResultV1
from .market_session_validation_v1 import MarketSessionValidationV1
from .multi_timeframe_snapshot_v1 import MultiTimeframeSnapshotV1
from .option_chain_intelligence_result_v1 import OptionChainIntelligenceResultV1
from .option_contract_ranking_result_v1 import OptionContractRankingResultV1
from .technical_intelligence_result_v1 import TechnicalIntelligenceResultV1

_IDENTITIES = {
    ("NIFTY", "NSE", "NFO"),
    ("SENSEX", "BSE", "BFO"),
}
_EVIDENCE = {"READY", "UNAVAILABLE", "CONFLICTING", "BLOCKED"}
_DIRECTIONS = {
    "BULLISH",
    "BEARISH",
    "NEUTRAL",
    "UNAVAILABLE",
    "CONFLICTING",
}
_ELIGIBILITY = {
    "ELIGIBLE",
    "INELIGIBLE",
    "UNAVAILABLE",
    "CONFLICTING",
}
_REQUIRED_CANONICAL = (
    "freshness",
    "data_quality",
    "session",
    "technical",
    "multi_timeframe",
    "regime",
    "option_chain",
    "option_contract_eligibility",
)
_OPTIONAL_CONTEXT = ("broader_market", "external_context")
_PILLARS = (
    "price_action",
    "candlestick",
    "chart_pattern",
    "volume",
    "volatility",
    "oi",
    "oi_change",
    "pcr",
    "support_resistance",
    "max_pain",
    "iv",
    "greeks",
    "premium_behavior",
    "liquidity_spread",
)


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


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


def _freeze_json_value(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(name)
            frozen[key] = _freeze_json_value(item, name)
        return MappingProxyType(frozen)

    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_value(item, name) for item in value)

    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(name)
        return value

    raise ValueError(name)


def _frozen_mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(name)
    return _freeze_json_value(value, name)


def _identity_of(value: object) -> tuple[object, object] | None:
    missing = object()
    symbol = getattr(value, "underlying_symbol", getattr(value, "symbol", missing))
    exchange = getattr(value, "exchange", missing)
    if symbol is missing or exchange is missing:
        return None
    return symbol, exchange


def _eligible_ready(name: str, value: object) -> bool:
    if name in {"freshness", "data_quality"}:
        return (
            value.quality_status in {"VALID", "VALID_WITH_WARNINGS"}
            and not value.blockers
        )
    if name == "session":
        return (
            value.session_state == "REGULAR"
            and value.analysis_allowed
            and value.paper_preparation_allowed
            and not value.stale
            and not value.future_timestamp
            and not value.blockers
            and not value.errors
        )
    if name == "technical":
        return value.status == "READY" and not value.blockers
    if name == "multi_timeframe":
        return (
            bool(value.timeframe_evidence)
            and not value.blockers
            and all(
                item.quality_status == "VALID"
                and item.history_sufficient
                and item.latest_candle_complete
                for item in value.timeframe_evidence
            )
        )
    if name == "regime":
        return (
            value.context_status == "READY"
            and value.primary_regime
            not in {"UNAVAILABLE", "CONFLICTING", "BLOCKED"}
            and value.entry_suitability == "SUITABLE"
            and value.entry_restriction_state == "OPEN"
            and value.analysis_allowed
            and value.new_entries_allowed
            and not value.blockers
            and not value.contradictions
        )
    if name == "option_chain":
        return (
            value.intelligence_status == "READY"
            and bool(value.metrics)
            and not value.blockers
        )
    if name == "option_contract_eligibility":
        return (
            value.ranking_status == "RANKED"
            and value.selected_candidate is not None
            and not value.blockers
        )
    raise ValueError("unknown canonical evidence")


def _eligible_optional_context(name: str, value: object) -> bool:
    if name == "broader_market":
        return (
            value.intelligence_status in {"READY", "READY_WITH_WARNINGS"}
            and value.aggregate_bias not in {"CONFLICTING", "UNAVAILABLE"}
            and not value.blockers
            and not value.contradictions
        )
    if name == "external_context":
        return (
            value.context_status in {"READY", "READY_WITH_WARNINGS"}
            and value.aggregate_direction not in {"CONFLICTING", "UNAVAILABLE"}
            and value.entry_restriction_state in {"OPEN", "WARNING"}
            and value.analysis_allowed
            and value.new_entries_allowed
            and not value.blockers
            and not value.contradictions
        )
    raise ValueError("unknown optional context")


@dataclass(frozen=True, slots=True)
class MarketAnalysisEvidenceV1:
    """Immutable evidence boundary for a pillar without an accepted V1 result."""

    status: str
    source_ids: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)
    summary: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = _text(self.status, "status").upper()
        if status not in _EVIDENCE:
            raise ValueError("status")

        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "source_ids",
            _messages(self.source_ids, "source_ids"),
        )
        object.__setattr__(
            self,
            "provenance",
            _frozen_mapping(self.provenance, "provenance"),
        )
        object.__setattr__(
            self,
            "summary",
            _frozen_mapping(self.summary, "summary"),
        )

        if status == "READY" and not self.source_ids:
            raise ValueError("ready evidence requires source_id")
        if status == "READY" and not (self.provenance or self.summary):
            raise ValueError("ready evidence requires retained detail")


@dataclass(frozen=True, slots=True)
class MarketAnalysisCandidateV1:
    """Supplied immutable evidence for one NIFTY or SENSEX PAPER analysis."""

    candidate_id: str
    observation_id: str
    underlying_symbol: str
    exchange: str
    option_exchange: str
    symboltoken: str
    requested_at: datetime
    market_timestamp: datetime
    received_at: datetime

    freshness: MarketDataQualityResultV1 | None
    data_quality: MarketDataQualityResultV1 | None
    session: MarketSessionValidationV1 | None
    technical: TechnicalIntelligenceResultV1 | None
    multi_timeframe: MultiTimeframeSnapshotV1 | None
    regime: CanonicalMarketRegimeResultV1 | None
    option_chain: OptionChainIntelligenceResultV1 | None
    option_contract_eligibility: OptionContractRankingResultV1 | None
    broader_market: BroaderMarketIntelligenceResultV1 | None
    external_context: ExternalMarketContextResultV1 | None

    price_action: MarketAnalysisEvidenceV1
    candlestick: MarketAnalysisEvidenceV1
    chart_pattern: MarketAnalysisEvidenceV1
    volume: MarketAnalysisEvidenceV1
    volatility: MarketAnalysisEvidenceV1
    oi: MarketAnalysisEvidenceV1
    oi_change: MarketAnalysisEvidenceV1
    pcr: MarketAnalysisEvidenceV1
    support_resistance: MarketAnalysisEvidenceV1
    max_pain: MarketAnalysisEvidenceV1
    iv: MarketAnalysisEvidenceV1
    greeks: MarketAnalysisEvidenceV1
    premium_behavior: MarketAnalysisEvidenceV1
    liquidity_spread: MarketAnalysisEvidenceV1

    direction: str
    eligibility: str
    confidence: float
    score: float

    contradictions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    evidence_references: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)

    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in ("candidate_id", "observation_id", "symboltoken"):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        identity = tuple(
            _text(getattr(self, name), name).upper()
            for name in ("underlying_symbol", "exchange", "option_exchange")
        )
        if identity not in _IDENTITIES:
            raise ValueError("unsupported market identity")

        for name, value in zip(
            ("underlying_symbol", "exchange", "option_exchange"),
            identity,
        ):
            object.__setattr__(self, name, value)

        requested = _aware(self.requested_at, "requested_at")
        market = _aware(self.market_timestamp, "market_timestamp")
        received = _aware(self.received_at, "received_at")
        if market > requested or requested > received:
            raise ValueError("timestamp ordering")

        for name, value in (
            ("requested_at", requested),
            ("market_timestamp", market),
            ("received_at", received),
        ):
            object.__setattr__(self, name, value)

        nested = (
            ("freshness", MarketDataQualityResultV1),
            ("data_quality", MarketDataQualityResultV1),
            ("session", MarketSessionValidationV1),
            ("technical", TechnicalIntelligenceResultV1),
            ("multi_timeframe", MultiTimeframeSnapshotV1),
            ("regime", CanonicalMarketRegimeResultV1),
            ("option_chain", OptionChainIntelligenceResultV1),
            ("option_contract_eligibility", OptionContractRankingResultV1),
            ("broader_market", BroaderMarketIntelligenceResultV1),
            ("external_context", ExternalMarketContextResultV1),
        )
        for name, kind in nested:
            value = getattr(self, name)
            if value is not None and type(value) is not kind:
                raise TypeError(name)
            if value is not None:
                child_identity = _identity_of(value)
                if child_identity is not None and child_identity != identity[:2]:
                    raise ValueError(f"{name} identity mismatch")

        for name in _PILLARS:
            if type(getattr(self, name)) is not MarketAnalysisEvidenceV1:
                raise TypeError(name)

        direction = _text(self.direction, "direction").upper()
        eligibility = _text(self.eligibility, "eligibility").upper()
        if direction not in _DIRECTIONS or eligibility not in _ELIGIBILITY:
            raise ValueError("direction or eligibility")

        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "eligibility", eligibility)

        for name in ("confidence", "score"):
            value = getattr(self, name)
            if (
                type(value) not in (int, float)
                or isinstance(value, bool)
                or not math.isfinite(value)
                or not 0.0 <= value <= 100.0
            ):
                raise ValueError(name)
            object.__setattr__(self, name, float(value))

        for name in (
            "contradictions",
            "warnings",
            "blockers",
            "reasons",
            "invalidation_conditions",
        ):
            object.__setattr__(
                self,
                name,
                _messages(getattr(self, name), name),
            )

        missing_required = tuple(
            name
            for name in _REQUIRED_CANONICAL
            if getattr(self, name) is None
        )
        nonready = tuple(
            name
            for name in _REQUIRED_CANONICAL
            if getattr(self, name) is not None
            and not _eligible_ready(name, getattr(self, name))
        )
        nonready_optional = tuple(
            name
            for name in _OPTIONAL_CONTEXT
            if getattr(self, name) is not None
            and not _eligible_optional_context(name, getattr(self, name))
        )
        unavailable_pillars = tuple(
            name
            for name in _PILLARS
            if getattr(self, name).status
            in {"UNAVAILABLE", "BLOCKED", "CONFLICTING"}
        )

        has_diagnostic = bool(self.blockers or self.contradictions)

        if (
            missing_required or nonready or nonready_optional
        ) and eligibility != "ELIGIBLE" and not has_diagnostic:
            raise ValueError(
                "missing or non-ready canonical evidence requires blocker or contradiction"
            )

        if (
            unavailable_pillars
            or direction in {"UNAVAILABLE", "CONFLICTING"}
            or eligibility in {"UNAVAILABLE", "CONFLICTING"}
        ) and not has_diagnostic:
            raise ValueError(
                "unavailable/conflicting evidence requires blocker or contradiction"
            )

        if eligibility == "ELIGIBLE" and (
            missing_required
            or nonready
            or nonready_optional
            or self.blockers
            or unavailable_pillars
            or direction not in {"BULLISH", "BEARISH"}
            or self.confidence == 0.0
            or self.score == 0.0
        ):
            raise ValueError(
                "eligible candidate cannot contain blocking, unavailable, or non-ready evidence"
            )

        if (
            self.confidence == 0.0 or self.score == 0.0
        ) and eligibility != "ELIGIBLE" and not has_diagnostic:
            raise ValueError(
                "zero unavailable score requires blocker or contradiction"
            )

        object.__setattr__(
            self,
            "evidence_references",
            _frozen_mapping(
                self.evidence_references,
                "evidence_references",
            ),
        )
        object.__setattr__(
            self,
            "provenance",
            _frozen_mapping(self.provenance, "provenance"),
        )

        if eligibility == "ELIGIBLE" and (
            not self.evidence_references or not self.provenance
        ):
            raise ValueError("eligible candidate requires traceable evidence")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.schema_version != "1.0"
        ):
            raise ValueError("PAPER-only contract")

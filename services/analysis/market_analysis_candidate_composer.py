"""Pure supplied-evidence composition for one PAPER market candidate."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from services.contracts.broader_market_intelligence_result_v1 import (
    BroaderMarketIntelligenceResultV1,
)
from services.contracts.canonical_market_regime_result_v1 import (
    CanonicalMarketRegimeResultV1,
)
from services.contracts.external_market_context_result_v1 import (
    ExternalMarketContextResultV1,
)
from services.contracts.market_analysis_candidate_v1 import (
    MarketAnalysisCandidateV1,
    MarketAnalysisEvidenceV1,
)
from services.contracts.market_data_quality_result_v1 import MarketDataQualityResultV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.multi_timeframe_snapshot_v1 import MultiTimeframeSnapshotV1
from services.contracts.option_chain_intelligence_result_v1 import (
    OptionChainIntelligenceResultV1,
)
from services.contracts.option_contract_ranking_result_v1 import (
    OptionContractRankingResultV1,
)
from services.contracts.technical_intelligence_result_v1 import (
    TechnicalIntelligenceResultV1,
)
from services.analysis.canonical_evidence_usability import (
    is_usable_option_intelligence_status,
    is_usable_option_ranking_status,
    is_usable_regime_status,
    is_usable_technical_status,
)

_IDENTITIES = {
    ("NIFTY", "NSE", "NFO"),
    ("SENSEX", "BSE", "BFO"),
}
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
_REQUIRED = (
    "freshness",
    "data_quality",
    "session",
    "technical",
    "multi_timeframe",
    "regime",
    "option_chain",
    "option_contract_eligibility",
)
_OPTIONAL = ("broader_market", "external_context")
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
_TYPES = {
    "freshness": MarketDataQualityResultV1,
    "data_quality": MarketDataQualityResultV1,
    "session": MarketSessionValidationV1,
    "technical": TechnicalIntelligenceResultV1,
    "multi_timeframe": MultiTimeframeSnapshotV1,
    "regime": CanonicalMarketRegimeResultV1,
    "option_chain": OptionChainIntelligenceResultV1,
    "option_contract_eligibility": OptionContractRankingResultV1,
    "broader_market": BroaderMarketIntelligenceResultV1,
    "external_context": ExternalMarketContextResultV1,
}


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


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _frozen_mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(name)
    try:
        payload = json.loads(
            json.dumps(dict(value), sort_keys=True, allow_nan=False)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(name) from exc
    return _freeze_json(payload)


def _identity_of(value: object) -> tuple[object, object] | None:
    missing = object()
    symbol = getattr(value, "underlying_symbol", getattr(value, "symbol", missing))
    exchange = getattr(value, "exchange", missing)
    if symbol is missing or exchange is missing:
        return None
    return symbol, exchange


def _ready(name: str, value: object) -> bool:
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
        return is_usable_technical_status(value.status) and not value.blockers
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
            is_usable_regime_status(value.context_status)
            and value.primary_regime
            not in {"UNAVAILABLE", "CONFLICTING", "BLOCKED"}
            and value.entry_suitability == "SUITABLE"
            and value.entry_restriction_state in {"OPEN", "WARNING"}
            and value.analysis_allowed
            and value.new_entries_allowed
            and not value.blockers
            and not value.contradictions
        )
    if name == "option_chain":
        return (
            is_usable_option_intelligence_status(value.intelligence_status)
            and bool(value.metrics)
            and not value.blockers
        )
    if name == "option_contract_eligibility":
        return (
            is_usable_option_ranking_status(value.ranking_status)
            and value.selected_candidate is not None
            and not value.blockers
        )
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
    raise ValueError(name)


@dataclass(frozen=True, slots=True)
class MarketAnalysisCandidateCompositionPolicyV1:
    """Explicit per-market output policy; no analysis is calculated here."""

    direction: str
    eligibility: str
    confidence: float
    score: float
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        direction = _text(self.direction, "direction").upper()
        eligibility = _text(self.eligibility, "eligibility").upper()
        if direction not in _DIRECTIONS:
            raise ValueError("direction")
        if eligibility not in _ELIGIBILITY:
            raise ValueError("eligibility")
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
            "blockers",
            "warnings",
            "contradictions",
            "reasons",
            "invalidation_conditions",
        ):
            object.__setattr__(self, name, _messages(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class MarketAnalysisCandidateCompositionInputV1:
    """Already-built immutable evidence for one supplied market observation."""

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
    evidence_references: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)

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
            ("underlying_symbol", "exchange", "option_exchange"), identity
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

        for name, kind in _TYPES.items():
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

        object.__setattr__(
            self,
            "evidence_references",
            _frozen_mapping(self.evidence_references, "evidence_references"),
        )
        object.__setattr__(
            self,
            "provenance",
            _frozen_mapping(self.provenance, "provenance"),
        )


def compose_market_analysis_candidate(
    composition: MarketAnalysisCandidateCompositionInputV1,
    policy: MarketAnalysisCandidateCompositionPolicyV1,
) -> MarketAnalysisCandidateV1:
    """Return one deterministic candidate from supplied evidence and policy only."""
    if type(composition) is not MarketAnalysisCandidateCompositionInputV1:
        raise TypeError("composition must be MarketAnalysisCandidateCompositionInputV1")
    if type(policy) is not MarketAnalysisCandidateCompositionPolicyV1:
        raise TypeError("policy must be MarketAnalysisCandidateCompositionPolicyV1")

    missing = tuple(
        name for name in _REQUIRED if getattr(composition, name) is None
    )
    nonready = tuple(
        name
        for name in _REQUIRED
        if getattr(composition, name) is not None
        and not _ready(name, getattr(composition, name))
    )
    optional_nonready = tuple(
        name
        for name in _OPTIONAL
        if getattr(composition, name) is not None
        and not _ready(name, getattr(composition, name))
    )
    pillar_nonready = tuple(
        name
        for name in _PILLARS
        if getattr(composition, name).status != "READY"
    )

    blockers = policy.blockers
    evidence_warnings = tuple(
        message
        for name in (*_REQUIRED, *_OPTIONAL)
        if getattr(composition, name) is not None
        for message in getattr(getattr(composition, name), "warnings", ())
    )
    warnings = tuple(dict.fromkeys(policy.warnings + evidence_warnings))
    contradictions = policy.contradictions
    direction = policy.direction
    eligibility = policy.eligibility
    confidence = policy.confidence
    score = policy.score

    if contradictions:
        direction = "CONFLICTING"
        eligibility = "CONFLICTING"
        confidence = 0.0
        score = 0.0
    elif missing or nonready or optional_nonready or pillar_nonready:
        failures = tuple(
            sorted(
                set(missing + nonready + optional_nonready + pillar_nonready)
            )
        )
        blockers = tuple(
            dict.fromkeys(
                blockers
                + tuple(
                    f"EVIDENCE_UNAVAILABLE_{name.upper()}"
                    for name in failures
                )
            )
        )
        direction = "UNAVAILABLE"
        eligibility = "UNAVAILABLE"
        confidence = 0.0
        score = 0.0
    elif blockers:
        direction = (
            direction if direction in {"BULLISH", "BEARISH"} else "UNAVAILABLE"
        )
        eligibility = "INELIGIBLE"
        confidence = 0.0
        score = 0.0
    elif direction == "NEUTRAL":
        blockers = ("DIRECTION_NEUTRAL_NO_TRADE",)
        eligibility = "INELIGIBLE"
        confidence = 0.0
        score = 0.0
    elif eligibility != "ELIGIBLE":
        blockers = ("POLICY_INELIGIBLE",)
        eligibility = "INELIGIBLE"
        confidence = 0.0
        score = 0.0

    values = {
        name: getattr(composition, name)
        for name in (*_REQUIRED, *_OPTIONAL, *_PILLARS)
    }
    return MarketAnalysisCandidateV1(
        candidate_id=composition.candidate_id,
        observation_id=composition.observation_id,
        underlying_symbol=composition.underlying_symbol,
        exchange=composition.exchange,
        option_exchange=composition.option_exchange,
        symboltoken=composition.symboltoken,
        requested_at=composition.requested_at,
        market_timestamp=composition.market_timestamp,
        received_at=composition.received_at,
        direction=direction,
        eligibility=eligibility,
        confidence=confidence,
        score=score,
        blockers=blockers,
        warnings=warnings,
        contradictions=contradictions,
        reasons=policy.reasons,
        invalidation_conditions=policy.invalidation_conditions,
        evidence_references=composition.evidence_references,
        provenance=composition.provenance,
        **values,
    )

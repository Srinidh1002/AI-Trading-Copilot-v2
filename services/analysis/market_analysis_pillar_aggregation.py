"""Canonical structural aggregation for Task 8's fourteen evidence pillars."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from services.contracts.market_analysis_candidate_v1 import MarketAnalysisEvidenceV1


PILLAR_ORDER = (
    "price_action", "candlestick", "chart_pattern", "volume", "volatility",
    "oi", "oi_change", "pcr", "support_resistance", "max_pain", "iv",
    "greeks", "premium_behavior", "liquidity_spread",
)


def _messages(values):
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _summary_messages(evidence, key):
    value = evidence.summary.get(key, ())
    return _messages(value if isinstance(value, (tuple, list)) else ())


@dataclass(frozen=True, slots=True)
class MarketAnalysisPillarAggregationResultV1:
    ordered_pillars: Mapping[str, MarketAnalysisEvidenceV1]
    evaluated_at: datetime
    aggregation_status: str
    ready_count: int
    unavailable_count: int
    blocked_count: int
    conflicting_count: int
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    schema_version: str = "market_analysis_pillar_aggregation.v1"

    def __post_init__(self):
        if not isinstance(self.evaluated_at, datetime) or self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at")
        if tuple(self.ordered_pillars) != PILLAR_ORDER or not all(type(self.ordered_pillars[name]) is MarketAnalysisEvidenceV1 for name in PILLAR_ORDER):
            raise ValueError("exact ordered pillar evidence required")
        if self.aggregation_status not in {"READY", "UNAVAILABLE", "BLOCKED", "CONFLICTING"}:
            raise ValueError("aggregation_status")
        object.__setattr__(self, "ordered_pillars", MappingProxyType(dict(self.ordered_pillars)))
        for name in ("blockers", "warnings", "contradictions", "reasons", "invalidation_conditions"):
            object.__setattr__(self, name, _messages(getattr(self, name)))

    def to_dict(self):
        return {"pillar_order": list(PILLAR_ORDER), "evaluated_at": self.evaluated_at.isoformat(), "aggregation_status": self.aggregation_status, "ready_count": self.ready_count, "unavailable_count": self.unavailable_count, "blocked_count": self.blocked_count, "conflicting_count": self.conflicting_count, "blockers": list(self.blockers), "warnings": list(self.warnings), "contradictions": list(self.contradictions), "reasons": list(self.reasons), "invalidation_conditions": list(self.invalidation_conditions), "schema_version": self.schema_version}


def aggregate_market_analysis_pillars(*, pillars: Mapping[str, MarketAnalysisEvidenceV1], evaluated_at: datetime) -> MarketAnalysisPillarAggregationResultV1:
    """Aggregate statuses only. Precedence is BLOCKED → UNAVAILABLE → CONFLICTING → READY."""
    if not isinstance(pillars, Mapping) or set(pillars) != set(PILLAR_ORDER):
        raise ValueError("exact fourteen pillars required")
    ordered = {name: pillars[name] for name in PILLAR_ORDER}
    if not all(type(value) is MarketAnalysisEvidenceV1 for value in ordered.values()):
        raise TypeError("pillar evidence")
    statuses = tuple(value.status for value in ordered.values())
    blockers = _messages(message for value in ordered.values() for message in _summary_messages(value, "blockers"))
    warnings = _messages(message for value in ordered.values() for message in _summary_messages(value, "warnings"))
    contradictions = _messages(message for value in ordered.values() for message in _summary_messages(value, "contradictions"))
    reasons = _messages(message for value in ordered.values() for message in _summary_messages(value, "reasons"))
    invalidation = _messages(message for value in ordered.values() for message in _summary_messages(value, "invalidation_conditions"))
    blocked = sum(status == "BLOCKED" for status in statuses)
    unavailable = sum(status == "UNAVAILABLE" for status in statuses)
    conflicting = sum(status == "CONFLICTING" for status in statuses)
    status = "BLOCKED" if blocked or blockers else "UNAVAILABLE" if unavailable else "CONFLICTING" if conflicting or contradictions else "READY"
    return MarketAnalysisPillarAggregationResultV1(ordered, evaluated_at, status, sum(value == "READY" for value in statuses), unavailable, blocked, conflicting, blockers, warnings, contradictions, reasons, invalidation)

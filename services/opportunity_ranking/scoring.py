"""Pure deterministic scoring for one normalized market opportunity candidate."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from services.contracts.four_market_ranking_policy_v1 import (
    DEFAULT_FOUR_MARKET_RANKING_POLICY,
    FourMarketRankingPolicyV1,
)
from services.contracts.market_opportunity_candidate_v1 import MarketOpportunityCandidateV1

from .eligibility import CandidateEligibilityEvaluationV1


_DIMENSIONS = (
    ("OPPORTUNITY_CONFIDENCE", "opportunity_confidence", "opportunity_confidence_weight", None),
    ("REGIME_SUITABILITY", "regime_suitability_score", "regime_suitability_weight", None),
    ("TECHNICAL_CONFIRMATION", "technical_confirmation_score", "technical_confirmation_weight", None),
    ("OPTION_CHAIN_CONFIRMATION", "option_chain_confirmation_score", "option_chain_confirmation_weight", "option_chain_available"),
    ("BROADER_MARKET_CONFIRMATION", "broader_market_confirmation_score", "broader_market_confirmation_weight", "broader_market_available"),
    ("EXTERNAL_CONTEXT_CONFIRMATION", "external_context_confirmation_score", "external_context_confirmation_weight", "external_context_available"),
    ("DATA_QUALITY", "data_quality_score", "data_quality_weight", None),
    ("LIQUIDITY", "liquidity_score", "liquidity_weight", "liquidity_available"),
    ("EXECUTION_QUALITY", "execution_quality_score", "execution_quality_weight", "execution_quality_available"),
)
_ELIGIBILITY = {"ELIGIBLE", "ELIGIBLE_WITH_WARNINGS", "CONFLICTING", "BLOCKED", "UNAVAILABLE"}


def _unique(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _freeze_records(records: dict[str, dict[str, float | bool]]) -> Mapping[str, Mapping[str, float | bool]]:
    return MappingProxyType(
        {name: MappingProxyType(dict(record)) for name, record in records.items()}
    )


@dataclass(frozen=True, slots=True)
class CandidateRankingScoreV1:
    """Immutable score diagnostics for exactly one market candidate."""

    underlying_symbol: str
    exchange: str
    eligibility_state: str
    rankable: bool
    raw_weighted_score: float
    usable_weight_sum: float
    normalized_base_score: float
    final_score: float
    applied_penalties: Mapping[str, float]
    excluded_dimensions: tuple[str, ...]
    component_contributions: Mapping[str, Mapping[str, float | bool]]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.underlying_symbol) is not str or type(self.exchange) is not str:
            raise TypeError("identity")
        if self.eligibility_state not in _ELIGIBILITY or type(self.rankable) is not bool:
            raise ValueError("eligibility")
        for name in ("raw_weighted_score", "usable_weight_sum", "normalized_base_score", "final_score"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(float(value)):
                raise ValueError(name)
            object.__setattr__(self, name, float(value))
        if not isinstance(self.applied_penalties, Mapping):
            raise TypeError("applied_penalties")
        penalties: dict[str, float] = {}
        for name, value in self.applied_penalties.items():
            if type(name) is not str or type(value) not in (int, float) or not math.isfinite(float(value)):
                raise ValueError("applied_penalties")
            penalties[name] = float(value)
        object.__setattr__(self, "applied_penalties", MappingProxyType(penalties))
        if type(self.excluded_dimensions) is not tuple or any(type(name) is not str for name in self.excluded_dimensions):
            raise TypeError("excluded_dimensions")
        if not isinstance(self.component_contributions, Mapping):
            raise TypeError("component_contributions")
        records: dict[str, dict[str, float | bool]] = {}
        for name, record in self.component_contributions.items():
            if type(name) is not str or not isinstance(record, Mapping):
                raise TypeError("component_contributions")
            value, weight, usable, contribution = (record.get(key) for key in ("value", "weight", "usable", "weighted_contribution"))
            if type(usable) is not bool or any(type(item) not in (int, float) or not math.isfinite(float(item)) for item in (value, weight, contribution)):
                raise ValueError("component_contributions")
            records[name] = {"value": float(value), "weight": float(weight), "usable": usable, "weighted_contribution": float(contribution)}
        object.__setattr__(self, "component_contributions", _freeze_records(records))
        for name in ("warnings", "blockers"):
            values = getattr(self, name)
            if type(values) is not tuple or any(type(value) is not str for value in values):
                raise TypeError(name)
            object.__setattr__(self, name, _unique(values))

    def to_dict(self) -> dict[str, Any]:
        return {
            "underlying_symbol": self.underlying_symbol,
            "exchange": self.exchange,
            "eligibility_state": self.eligibility_state,
            "rankable": self.rankable,
            "raw_weighted_score": self.raw_weighted_score,
            "usable_weight_sum": self.usable_weight_sum,
            "normalized_base_score": self.normalized_base_score,
            "final_score": self.final_score,
            "applied_penalties": _json_safe(self.applied_penalties),
            "excluded_dimensions": list(self.excluded_dimensions),
            "component_contributions": _json_safe(self.component_contributions),
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def semantic_dict(self) -> dict[str, Any]:
        return self.to_dict()


def score_market_opportunity_candidate(
    candidate: MarketOpportunityCandidateV1,
    eligibility: CandidateEligibilityEvaluationV1,
    policy: FourMarketRankingPolicyV1 = DEFAULT_FOUR_MARKET_RANKING_POLICY,
) -> CandidateRankingScoreV1:
    """Score one candidate; eligibility ownership remains with P5-11E."""
    if type(candidate) is not MarketOpportunityCandidateV1:
        raise TypeError("candidate")
    if type(eligibility) is not CandidateEligibilityEvaluationV1:
        raise TypeError("eligibility")
    if type(policy) is not FourMarketRankingPolicyV1:
        raise TypeError("policy")
    if (candidate.underlying_symbol, candidate.exchange) != (eligibility.underlying_symbol, eligibility.exchange):
        raise ValueError("candidate and eligibility identity mismatch")

    records: dict[str, dict[str, float | bool]] = {}
    excluded: list[str] = []
    warnings = list(eligibility.warnings)
    blockers = list(eligibility.blockers)
    raw_score = 0.0
    usable_weight_sum = 0.0
    for name, candidate_field, policy_field, availability_field in _DIMENSIONS:
        value = float(getattr(candidate, candidate_field))
        weight = float(getattr(policy, policy_field))
        available = availability_field is None or getattr(candidate, availability_field)
        usable = available or not policy.exclude_unavailable_optional_scores_from_denominator
        contribution = weight * value if usable else 0.0
        if not usable:
            excluded.append(name)
            warnings.append(f"EXCLUDED_{name}")
        records[name] = {
            "value": value,
            "weight": weight,
            "usable": usable,
            "weighted_contribution": contribution,
        }
        if usable:
            raw_score += contribution
            usable_weight_sum += weight

    if usable_weight_sum > 0.0:
        normalized_base_score = min(1.0, max(0.0, raw_score / usable_weight_sum))
    else:
        normalized_base_score = 0.0
        blockers.append("NO_USABLE_SCORE_WEIGHT")
        warnings.append("NO_USABLE_SCORE_WEIGHT")

    penalties: dict[str, float] = {}
    warning_condition = bool(eligibility.warnings or candidate.warnings or eligibility.eligibility_state == "ELIGIBLE_WITH_WARNINGS")
    if warning_condition:
        penalties["WARNING"] = policy.warning_penalty
        warnings.append("WARNING_PENALTY_APPLIED")
    if eligibility.eligibility_state == "CONFLICTING" and policy.allow_conflicting_candidate_to_rank and eligibility.rankable:
        penalties["CONFLICT"] = policy.conflict_penalty
        warnings.append("CONFLICT_PENALTY_APPLIED")
    if eligibility.missing_optional_references and policy.apply_missing_optional_evidence_penalty_once:
        penalties["MISSING_OPTIONAL_EVIDENCE"] = policy.missing_optional_evidence_penalty
        warnings.append("MISSING_OPTIONAL_EVIDENCE_PENALTY_APPLIED")
    if eligibility.freshness_failure in {"STALE", "MIXED"} or candidate.freshness_state in {"STALE", "MIXED"}:
        penalties["STALE_DATA"] = policy.stale_data_penalty
        warnings.append("STALE_DATA_PENALTY_APPLIED")
    event_risk = candidate.market_regime.primary_regime == "EVENT_RISK" or candidate.market_regime.event_risk_state in {"HIGH", "EXTREME"}
    if event_risk and eligibility.rankable:
        penalties["EVENT_RISK"] = policy.event_risk_penalty
        warnings.append("EVENT_RISK_PENALTY_APPLIED")
    if eligibility.spread_limit_breach:
        penalties["SPREAD"] = policy.spread_penalty
        warnings.append("SPREAD_PENALTY_APPLIED")
    if eligibility.slippage_limit_breach:
        penalties["SLIPPAGE"] = policy.slippage_penalty
        warnings.append("SLIPPAGE_PENALTY_APPLIED")

    rankable = eligibility.rankable and usable_weight_sum > 0.0
    final_score = max(0.0, min(1.0, normalized_base_score - sum(penalties.values()))) if rankable else 0.0
    return CandidateRankingScoreV1(
        candidate.underlying_symbol,
        candidate.exchange,
        eligibility.eligibility_state,
        rankable,
        raw_score,
        usable_weight_sum,
        normalized_base_score,
        final_score,
        penalties,
        tuple(excluded),
        records,
        _unique(warnings),
        _unique(blockers),
    )

"""Fail-closed diagnostic boundary for persisted Task 9 evidence.

This module deliberately does not participate in production evaluation.  The
repository currently has no canonical inverse serializers for the nested
evaluation graph, so it refuses to manufacture typed evidence.
"""

from __future__ import annotations

import json
from dataclasses import MISSING, dataclass, fields, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Union, get_args, get_origin, get_type_hints
import types
from collections.abc import Mapping as ABCMapping

from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
from services.contracts.market_analysis_candidate_v1 import MarketAnalysisEvidenceV1
from services.contracts.market_data_quality_result_v1 import MarketDataQualityResultV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.multi_timeframe_snapshot_v1 import MultiTimeframeSnapshotV1
from services.contracts.option_chain_intelligence_result_v1 import OptionChainIntelligenceResultV1
from services.contracts.option_chain_metric_v1 import OptionChainMetricV1
from services.contracts.technical_indicator_value_v1 import TechnicalIndicatorValueV1
from services.contracts.technical_intelligence_result_v1 import TechnicalIntelligenceResultV1
from services.contracts.timeframe_technical_evidence_v1 import TimeframeTechnicalEvidenceV1
from services.contracts.timeframe_evidence_v1 import TimeframeEvidenceV1
from services.contracts.cross_market_evidence_v1 import CrossMarketEvidenceV1
from services.contracts.market_breadth_evidence_v1 import MarketBreadthEvidenceV1
from services.contracts.volatility_context_v1 import VolatilityContextV1
from services.contracts.technical_regime_component_result_v1 import TechnicalRegimeComponentResultV1
from services.contracts.broader_market_regime_component_result_v1 import BroaderMarketRegimeComponentResultV1
from services.contracts.external_context_regime_component_result_v1 import ExternalContextRegimeComponentResultV1
from services.analysis.market_analysis_candidate_composer import (
    MarketAnalysisCandidateCompositionInputV1,
    MarketAnalysisCandidateCompositionPolicyV1,
    compose_market_analysis_candidate,
)

from services.contracts.option_contract_candidate_v1 import (
    OptionContractCandidateV1,
)
from services.contracts.option_contract_ranking_result_v1 import (
    OptionContractRankingResultV1,
)
from services.contracts.option_contract_v1 import OptionContractV1


_TYPE_DISPATCH = {
    "MarketAnalysisCandidateCompositionInputV1": MarketAnalysisCandidateCompositionInputV1,
    "MarketAnalysisEvidenceV1": MarketAnalysisEvidenceV1,
    "MarketDataQualityResultV1": MarketDataQualityResultV1,
    "MarketSessionValidationV1": MarketSessionValidationV1,
    "TechnicalIndicatorValueV1": TechnicalIndicatorValueV1,
    "TimeframeTechnicalEvidenceV1": TimeframeTechnicalEvidenceV1,
    "TechnicalIntelligenceResultV1": TechnicalIntelligenceResultV1,
    "MultiTimeframeSnapshotV1": MultiTimeframeSnapshotV1,
    "CanonicalMarketRegimeResultV1": CanonicalMarketRegimeResultV1,
    "OptionChainMetricV1": OptionChainMetricV1,
    "OptionChainIntelligenceResultV1": OptionChainIntelligenceResultV1,
    "BroaderMarketIntelligenceResultV1": BroaderMarketIntelligenceResultV1,
    "ExternalMarketContextResultV1": ExternalMarketContextResultV1,
    "TimeframeEvidenceV1": TimeframeEvidenceV1,
    "CrossMarketEvidenceV1": CrossMarketEvidenceV1,
    "MarketBreadthEvidenceV1": MarketBreadthEvidenceV1,
    "VolatilityContextV1": VolatilityContextV1,
    "TechnicalRegimeComponentResultV1": TechnicalRegimeComponentResultV1,
    "BroaderMarketRegimeComponentResultV1": BroaderMarketRegimeComponentResultV1,
    "ExternalContextRegimeComponentResultV1": ExternalContextRegimeComponentResultV1,
    "OptionContractRankingResultV1": OptionContractRankingResultV1,
    "OptionContractCandidateV1": OptionContractCandidateV1,
    "OptionContractV1": OptionContractV1,
}


class RehydrationIncomplete(ValueError):
    """Persisted evidence cannot be reconstructed without fabrication."""

    code = "REHYDRATION_INCOMPLETE"


class RehydrationInvalid(ValueError):
    code = "REHYDRATION_INVALID"


class RehydrationTypeTagMismatch(ValueError):
    code = "REHYDRATION_TYPE_TAG_MISMATCH"


@dataclass(frozen=True)
class PersistedRankingIdentity:
    observation_id: str
    ranking_status: str
    directional_bias: str
    required_option_type: str | None
    ranked_candidate_count: int
    selected_contract_id: str | None


def _tag(value: Mapping[str, Any], expected: str, path: str, observation_id: str) -> None:
    actual = value.get("__type__")
    if actual != expected:
        raise RehydrationTypeTagMismatch(
            f"{RehydrationTypeTagMismatch.code}: {observation_id}: {path} "
            f"expected={expected} actual={actual}"
        )


def _datetime(value: Any, path: str, observation_id: str) -> datetime:
    if not isinstance(value, str):
        raise RehydrationInvalid(
            f"{RehydrationInvalid.code}: {observation_id}: {path} expected datetime string"
        )
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RehydrationInvalid(
            f"{RehydrationInvalid.code}: {observation_id}: {path} malformed datetime"
        ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise RehydrationInvalid(
            f"{RehydrationInvalid.code}: {observation_id}: {path} naive datetime"
        )
    return result


def _date(value: Any, path: str, observation_id: str) -> date:
    if not isinstance(value, str):
        raise RehydrationInvalid(
            f"{RehydrationInvalid.code}: {observation_id}: {path} expected date string"
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RehydrationInvalid(
            f"{RehydrationInvalid.code}: {observation_id}: {path} malformed date"
        ) from exc


def _rehydrate_graph(value: Any, expected: Any, *, observation_id: str, path: str) -> Any:
    """Explicitly-dispatched diagnostic reconstruction for the known graph."""
    if value is None:
        return None
    origin = get_origin(expected)
    args = get_args(expected)
    if origin in (Union, types.UnionType):
        choices = [item for item in args if item is not type(None)]
        if len(choices) == 1:
            return _rehydrate_graph(value, choices[0], observation_id=observation_id, path=path)
    if expected is datetime:
        return _datetime(value, path, observation_id)
    if expected is date:
        return _date(value, path, observation_id)
    if origin in (tuple,):
        if not isinstance(value, list):
            raise RehydrationInvalid(f"{RehydrationInvalid.code}: {observation_id}: {path} expected array")
        subtype = args[0] if args and args[0] is not Ellipsis else Any
        return tuple(_rehydrate_graph(item, subtype, observation_id=observation_id, path=f"{path}[{i}]") for i, item in enumerate(value))
    if origin in (dict, Mapping, ABCMapping):
        if not isinstance(value, Mapping):
            raise RehydrationInvalid(f"{RehydrationInvalid.code}: {observation_id}: {path} expected mapping")
        valtype = args[1] if len(args) > 1 else Any
        return {key: _rehydrate_graph(item, valtype, observation_id=observation_id, path=f"{path}.{key}") for key, item in value.items()}
    if expected in (Any, object) or expected is None:
        return value
    if isinstance(expected, type) and expected.__name__ in _TYPE_DISPATCH and isinstance(value, Mapping):
        actual = value.get("__type__")
        expected_tag = expected.__name__
        _tag(value, expected_tag, path, observation_id)
        if not is_dataclass(expected):
            return value
        hints = get_type_hints(expected)
        kwargs = {}
        for field in fields(expected):
            if field.name not in value:
                if field.default is MISSING and field.default_factory is MISSING:
                    raise RehydrationIncomplete(f"{RehydrationIncomplete.code}: {observation_id}: {path}.{field.name} missing")
                continue
            kwargs[field.name] = _rehydrate_graph(value[field.name], hints.get(field.name, Any), observation_id=observation_id, path=f"{path}.{field.name}")
        try:
            result = expected(**kwargs)
        except (TypeError, ValueError) as exc:
            raise RehydrationInvalid(f"{RehydrationInvalid.code}: {observation_id}: {path}: {exc}") from exc
        if type(result) is not expected:
            raise TypeError(f"REHYDRATION_TYPE_MISMATCH: {observation_id}: {path} expected={expected.__name__} actual={type(result).__name__}")
        return result
    return value


def rehydrate_market_analysis_composition(value: Mapping[str, Any], *, observation_id: str) -> MarketAnalysisCandidateCompositionInputV1:
    result = _rehydrate_graph(value, MarketAnalysisCandidateCompositionInputV1, observation_id=observation_id, path="$.composition")
    return result


def rehydrate_composition_policy(value: Mapping[str, Any], *, observation_id: str) -> MarketAnalysisCandidateCompositionPolicyV1:
    if not isinstance(value, Mapping):
        raise RehydrationIncomplete(f"{RehydrationIncomplete.code}: {observation_id}: $.policy expected mapping")
    _tag(value, "MarketAnalysisCandidateCompositionPolicyV1", "$.policy", observation_id)
    kwargs = {name: value[name] for name in ("direction", "eligibility", "confidence", "score") if name in value}
    missing = next((name for name in ("direction", "eligibility", "confidence", "score") if name not in kwargs), None)
    if missing:
        raise RehydrationIncomplete(f"{RehydrationIncomplete.code}: {observation_id}: $.policy.{missing} missing")
    for name in ("blockers", "warnings", "contradictions", "reasons", "invalidation_conditions"):
        kwargs[name] = tuple(value.get(name, ()))
    try:
        return MarketAnalysisCandidateCompositionPolicyV1(**kwargs)
    except (TypeError, ValueError) as exc:
        raise RehydrationInvalid(f"{RehydrationInvalid.code}: {observation_id}: $.policy: {exc}") from exc


def rehydrate_option_contract(
    value: Mapping[str, Any], *, observation_id: str, path: str
) -> OptionContractV1:
    if not isinstance(value, Mapping):
        raise RehydrationIncomplete(
            f"{RehydrationIncomplete.code}: {observation_id}: {path} expected mapping"
        )
    _tag(value, "OptionContractV1", path, observation_id)
    required = ("contract_id", "underlying_symbol", "exchange", "trading_symbol", "option_type", "strike", "expiry_date", "lot_size", "market_timestamp")
    missing = next((name for name in required if name not in value), None)
    if missing:
        raise RehydrationIncomplete(
            f"{RehydrationIncomplete.code}: {observation_id}: {path}.{missing} missing"
        )
    fields = {name: value[name] for name in OptionContractV1.__dataclass_fields__ if name in value}
    fields["expiry_date"] = _date(fields["expiry_date"], f"{path}.expiry_date", observation_id)
    fields["market_timestamp"] = _datetime(fields["market_timestamp"], f"{path}.market_timestamp", observation_id)
    fields.pop("schema_version", None)
    try:
        result = OptionContractV1(**fields)
    except (TypeError, ValueError) as exc:
        raise RehydrationInvalid(
            f"{RehydrationInvalid.code}: {observation_id}: {path}: {exc}"
        ) from exc
    if type(result) is not OptionContractV1:
        raise TypeError(f"REHYDRATION_TYPE_MISMATCH: {observation_id}: {path}")
    return result


def rehydrate_ranked_candidate(
    value: Mapping[str, Any], *, observation_id: str, path: str
) -> OptionContractCandidateV1:
    if not isinstance(value, Mapping):
        raise RehydrationIncomplete(
            f"{RehydrationIncomplete.code}: {observation_id}: {path} expected mapping"
        )
    _tag(value, "OptionContractCandidateV1", path, observation_id)
    contract = rehydrate_option_contract(value.get("contract"), observation_id=observation_id, path=f"{path}.contract")
    fields = {name: value[name] for name in OptionContractCandidateV1.__dataclass_fields__ if name in value and name != "contract"}
    fields["contract"] = contract
    for name in ("rejection_reasons", "warnings"):
        if name in fields:
            if not isinstance(fields[name], list):
                raise RehydrationInvalid(
                    f"{RehydrationInvalid.code}: {observation_id}: {path}.{name} expected persisted array"
                )
            fields[name] = tuple(fields[name])
    required = ("candidate_status", "moneyness", "strike_distance_percent", "liquidity_score", "proximity_score", "open_interest_score", "volume_score", "spread_score", "implied_volatility_score", "intelligence_alignment_score", "total_score")
    missing = next((name for name in required if name not in fields), None)
    if missing:
        raise RehydrationIncomplete(f"{RehydrationIncomplete.code}: {observation_id}: {path}.{missing} missing")
    try:
        result = OptionContractCandidateV1(**fields)
    except (TypeError, ValueError) as exc:
        raise RehydrationInvalid(f"{RehydrationInvalid.code}: {observation_id}: {path}: {exc}") from exc
    return result


def rehydrate_typed_option_ranking(
    value: Mapping[str, Any], *, observation_id: str, path: str
) -> OptionContractRankingResultV1:
    if not isinstance(value, Mapping):
        raise RehydrationIncomplete(f"{RehydrationIncomplete.code}: {observation_id}: {path} expected mapping")
    _tag(value, "OptionContractRankingResultV1", path, observation_id)
    ranked_raw = value.get("ranked_candidates")
    rejected_raw = value.get("rejected_candidates")
    if not isinstance(ranked_raw, list) or not isinstance(rejected_raw, list):
        raise RehydrationIncomplete(
            f"{RehydrationIncomplete.code}: {observation_id}: {path}.ranked_candidates/rejected_candidates expected persisted arrays"
        )
    ranked = tuple(rehydrate_ranked_candidate(item, observation_id=observation_id, path=f"{path}.ranked_candidates[{i}]") for i, item in enumerate(ranked_raw))
    rejected = tuple(rehydrate_ranked_candidate(item, observation_id=observation_id, path=f"{path}.rejected_candidates[{i}]") for i, item in enumerate(rejected_raw))
    fields = {
        "ranking_id": value.get("ranking_id"), "ranked_at": _datetime(value.get("ranked_at"), f"{path}.ranked_at", observation_id),
        "universe_id": value.get("universe_id"), "intelligence_result_id": value.get("intelligence_result_id"),
        "underlying_symbol": value.get("underlying_symbol"), "exchange": value.get("exchange"),
        "directional_bias": value.get("directional_bias"), "required_option_type": value.get("required_option_type"),
        "ranking_status": value.get("ranking_status"), "ranked_candidates": ranked, "rejected_candidates": rejected,
        "blockers": tuple(value.get("blockers", ())), "warnings": tuple(value.get("warnings", ())), "diagnostics": tuple(value.get("diagnostics", ())),
        "metadata": value.get("metadata", {}),
    }
    try:
        result = OptionContractRankingResultV1(**fields)
    except (TypeError, ValueError) as exc:
        raise RehydrationInvalid(f"{RehydrationInvalid.code}: {observation_id}: {path}: {exc}") from exc
    return result


def _snapshot(
    *,
    audit_path: str | Path,
    observation_id: str,
) -> Mapping[str, Any]:
    payload = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, Mapping):
        raise RehydrationIncomplete(
            f"{RehydrationIncomplete.code}: {observation_id}: "
            "$.records: expected mapping"
        )
    for record in records.values():
        if isinstance(record, Mapping) and record.get("observation_id") == observation_id:
            snapshot = record.get("evaluation_snapshot")
            if not isinstance(snapshot, Mapping):
                raise RehydrationIncomplete(
                    f"{RehydrationIncomplete.code}: {observation_id}: "
                    "$.evaluation_snapshot: required persisted mapping missing"
                )
            return snapshot
    raise RehydrationIncomplete(
        f"{RehydrationIncomplete.code}: {observation_id}: "
        "$.records[*].observation_id: observation not found"
    )


def rehydrate_option_ranking(
    ranking: Mapping[str, Any],
    *,
    observation_id: str,
) -> PersistedRankingIdentity:
    """Validate ranking identity without creating a fake typed ranking."""
    if not isinstance(ranking, Mapping):
        raise RehydrationIncomplete(
            f"{RehydrationIncomplete.code}: {observation_id}: "
            "$.candidate.option_contract_eligibility: expected mapping"
        )
    candidates = ranking.get("ranked_candidates")
    if not isinstance(candidates, list):
        raise RehydrationIncomplete(
            f"{RehydrationIncomplete.code}: {observation_id}: "
            "$.candidate.option_contract_eligibility.ranked_candidates: "
            "expected persisted list"
        )
    selected_id = None
    if candidates:
        first = candidates[0]
        contract = first.get("contract") if isinstance(first, Mapping) else None
        selected_id = contract.get("contract_id") if isinstance(contract, Mapping) else None
        if not isinstance(selected_id, str) or not selected_id:
            raise RehydrationIncomplete(
                f"{RehydrationIncomplete.code}: {observation_id}: "
                "$.candidate.option_contract_eligibility.ranked_candidates[0].contract.contract_id: "
                "required selected identity missing"
            )
    return PersistedRankingIdentity(
        observation_id=observation_id,
        ranking_status=str(ranking.get("ranking_status")),
        directional_bias=str(ranking.get("directional_bias")),
        required_option_type=ranking.get("required_option_type"),
        ranked_candidate_count=len(candidates),
        selected_contract_id=selected_id,
    )


def rehydrate_task9_evaluation_snapshot(
    *,
    audit_path: str | Path,
    observation_id: str,
) -> MarketAnalysisCandidateCompositionInputV1:
    snapshot = _snapshot(audit_path=audit_path, observation_id=observation_id)
    candidate = snapshot.get("candidate")
    if not isinstance(candidate, Mapping):
        raise RehydrationIncomplete(
            f"{RehydrationIncomplete.code}: {observation_id}: "
            "$.candidate: required persisted mapping missing"
        )
    ranking = candidate.get("option_contract_eligibility")
    identity = rehydrate_option_ranking(
        ranking,
        observation_id=observation_id,
    )
    typed_ranking = rehydrate_typed_option_ranking(
        ranking,
        observation_id=observation_id,
        path="$.candidate.option_contract_eligibility",
    )
    if typed_ranking.selected_candidate is None:
        raise RehydrationIncomplete(
            f"{RehydrationIncomplete.code}: {observation_id}: "
            "$.candidate.option_contract_eligibility.selected_candidate: "
            "derived selection is absent"
        )
    if identity.selected_contract_id != typed_ranking.selected_candidate.contract.contract_id:
        raise RehydrationIncomplete(
            f"{RehydrationIncomplete.code}: {observation_id}: "
            "$.candidate.option_contract_eligibility.selected_contract_id: "
            "derived identity mismatch"
        )
    composition = snapshot.get("composition")
    if not isinstance(composition, Mapping):
        raise RehydrationIncomplete(
            f"{RehydrationIncomplete.code}: {observation_id}: $.composition: required persisted mapping missing"
        )
    rehydrate_market_analysis_composition(composition, observation_id=observation_id)
    return rehydrate_market_analysis_composition(composition, observation_id=observation_id)

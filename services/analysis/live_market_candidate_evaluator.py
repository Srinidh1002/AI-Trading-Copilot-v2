"""One provider-free NIFTY or SENSEX typed candidate evaluation."""
from __future__ import annotations
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from services.analysis.live_canonical_evidence_engines import LiveCanonicalEvidenceEnginesV1, LiveCanonicalEvidenceResultV1, build_live_canonical_evidence
from services.analysis.live_typed_candidate_evidence import LiveTypedEvidenceInputV1, compose_from_live_canonical_evidence
from services.analysis.market_analysis_candidate_composer import MarketAnalysisCandidateCompositionInputV1, MarketAnalysisCandidateCompositionPolicyV1, compose_market_analysis_candidate
from services.contracts.market_analysis_candidate_v1 import MarketAnalysisCandidateV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.market.angel_live_observation_normalizer import AngelLiveMarketObservationV1, normalize_angel_live_observation
from services.options.angel_option_chain_normalizer import AngelOptionNormalizationResultV1, normalize_angel_option_chain
from services.paper_orchestration.certified_live_provider_readers import CertifiedIndexMarketSpecV1
from services.contracts.certified_live_captured_evidence_v1 import CertifiedLiveCapturedEvidenceV1
from services.paper_orchestration.certified_live_provider_readers import market_spec_for
from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
from services.analysis.market_analysis_confidence_ledger import build_market_analysis_confidence_ledger
from services.analysis.pre_entry_action_resolver import resolve_pre_entry_market_action

@dataclass(frozen=True,slots=True)
class LiveCandidatePolicySourceV1:
 direction:str;eligibility:str;confidence:float;score:float;reasons:tuple[str,...]=();invalidation_conditions:tuple[str,...]=();blockers:tuple[str,...]=();warnings:tuple[str,...]=();contradictions:tuple[str,...]=()
 def __post_init__(self):
  # Delegate vocabulary/range validation to the existing policy contract.
  MarketAnalysisCandidateCompositionPolicyV1(self.direction,self.eligibility,self.confidence,self.score,self.blockers,self.warnings,self.contradictions,self.reasons,self.invalidation_conditions)

 @classmethod
 def unavailable(cls, *, blockers:tuple[str,...]=(), reasons:tuple[str,...]=()):
  """Use the composer-defined unavailable numeric representation (0.0)."""
  return cls("UNAVAILABLE", "UNAVAILABLE", 0.0, 0.0, reasons=tuple(dict.fromkeys(("Authoritative policy evidence is unavailable.", *reasons))), blockers=tuple(dict.fromkeys(("CERTIFIED_POLICY_EVIDENCE_UNAVAILABLE", *blockers))))

@dataclass(frozen=True,slots=True)
class LiveMarketCandidateEvaluationInputV1:
 market_spec:CertifiedIndexMarketSpecV1;parent_cycle_id:str;candidate_id:str;observation_id:str;spot_response:object;candle_rows_by_timeframe:Mapping[str,object];option_contracts:object;option_chain_evidence_contracts:object|None;provider_timestamp:datetime;evaluated_at:datetime;session:MarketSessionValidationV1;policy:LiveCandidatePolicySourceV1;engines:LiveCanonicalEvidenceEnginesV1;broader_market:BroaderMarketIntelligenceResultV1|None=None;external_context:ExternalMarketContextResultV1|None=None;provider_state:str="OK";blockers:tuple[str,...]=();warnings:tuple[str,...]=()
 def __post_init__(self):
  if type(self.market_spec) is not CertifiedIndexMarketSpecV1 or type(self.session) is not MarketSessionValidationV1 or type(self.policy) is not LiveCandidatePolicySourceV1 or type(self.engines) is not LiveCanonicalEvidenceEnginesV1:raise TypeError("typed evaluation input")
  if type(self.parent_cycle_id) is not str or not self.parent_cycle_id.strip():raise ValueError("parent_cycle_id")
  if self.provider_timestamp.tzinfo is None or self.evaluated_at.tzinfo is None:raise ValueError("timestamps")
  if (self.session.symbol,self.session.exchange)!=(self.market_spec.underlying_symbol,self.market_spec.exchange):raise ValueError("session identity")
  if self.broader_market is not None and (type(self.broader_market) is not BroaderMarketIntelligenceResultV1 or (self.broader_market.underlying_symbol,self.broader_market.exchange)!=(self.market_spec.underlying_symbol,self.market_spec.exchange)):raise ValueError("broader market identity")
  if self.external_context is not None and (type(self.external_context) is not ExternalMarketContextResultV1 or (self.external_context.underlying_symbol,self.external_context.exchange)!=(self.market_spec.underlying_symbol,self.market_spec.exchange) or self.external_context.created_at != self.evaluated_at):raise ValueError("external context identity or evaluation boundary")

@dataclass(frozen=True,slots=True)
class LiveMarketCandidateEvaluationResultV1:
 observation:AngelLiveMarketObservationV1;options:AngelOptionNormalizationResultV1;evidence:LiveCanonicalEvidenceResultV1;composition:MarketAnalysisCandidateCompositionInputV1;policy:MarketAnalysisCandidateCompositionPolicyV1;candidate:MarketAnalysisCandidateV1;pre_entry_action:object|None=None

def _build_live_candidate_base_evidence(
    value: LiveMarketCandidateEvaluationInputV1,
) -> tuple[
    AngelLiveMarketObservationV1,
    AngelOptionNormalizationResultV1,
    LiveCanonicalEvidenceResultV1,
]:
    """Build normalized market/options and canonical evidence exactly once."""
    if type(value) is not LiveMarketCandidateEvaluationInputV1:
        raise TypeError("evaluation input")

    observation = normalize_angel_live_observation(
        spot_response=value.spot_response,
        candle_rows_by_timeframe=(
            value.candle_rows_by_timeframe
        ),
        market_spec=value.market_spec,
        provider_timestamp=value.provider_timestamp,
        evaluated_at=value.evaluated_at,
        provider_state=value.provider_state,
        blockers=value.blockers,
        warnings=value.warnings,
    )

    options = normalize_angel_option_chain(
        contracts=value.option_contracts,
        snapshot_contracts=(
            value.option_chain_evidence_contracts
            if value.option_chain_evidence_contracts is not None
            else value.option_contracts
        ),
        market_spec=value.market_spec,
        spot_price=observation.spot.price,
        provider_timestamp=value.provider_timestamp,
        evaluated_at=value.evaluated_at,
        provider_state=value.provider_state,
        blockers=value.blockers,
        warnings=value.warnings,
    )

    evidence = build_live_canonical_evidence(
        observation=observation,
        options=options,
        session=value.session,
        evaluated_at=value.evaluated_at,
        engines=value.engines,
        cycle_id=value.candidate_id,
        observation_id=value.observation_id,
        broader_market=value.broader_market,
        external_context=value.external_context,
        blockers=value.blockers,
        warnings=value.warnings,
    )

    return observation, options, evidence


def _finalize_live_market_candidate(
    *,
    value: LiveMarketCandidateEvaluationInputV1,
    observation: AngelLiveMarketObservationV1,
    options: AngelOptionNormalizationResultV1,
    evidence: LiveCanonicalEvidenceResultV1,
    policy: LiveCandidatePolicySourceV1,
) -> LiveMarketCandidateEvaluationResultV1:
    """Apply one already-decided policy to one already-built evidence graph."""
    if type(policy) is not LiveCandidatePolicySourceV1:
        raise TypeError(
            "policy factory must return exact "
            "LiveCandidatePolicySourceV1"
        )

    # These fields historically entered the evidence result from the
    # supplied policy before canonical evidence construction. They are
    # metadata only; no canonical evidence engine consumes them.
    evidence = replace(
        evidence,
        contradictions=policy.contradictions,
        reasons=policy.reasons,
        invalidation_conditions=(
            policy.invalidation_conditions
        ),
    )

    source = LiveTypedEvidenceInputV1(
        value.candidate_id,
        value.observation_id,
        value.market_spec.underlying_symbol,
        value.market_spec.exchange,
        value.market_spec.option_exchange,
        value.market_spec.symboltoken,
        value.evaluated_at,
        value.provider_timestamp,
        value.evaluated_at,
        observation,
        options,
        value.session,
        policy.direction,
        policy.eligibility,
        policy.confidence,
        policy.score,
        policy.reasons,
        policy.invalidation_conditions,
        policy.blockers,
        policy.warnings,
        policy.contradictions,
    )

    evidence = replace(
        evidence,
        confidence_ledger=(
            build_market_analysis_confidence_ledger(
                cycle_id=value.parent_cycle_id,
                observation_id=value.observation_id,
                evidence=evidence,
                policy_source=policy,
            )
        ),
    )

    composition, composition_policy = (
        compose_from_live_canonical_evidence(
            source=source,
            evidence=evidence,
        )
    )

    candidate = compose_market_analysis_candidate(
        composition,
        composition_policy,
    )

    action = resolve_pre_entry_market_action(
        candidate=candidate,
        cycle_id=value.parent_cycle_id,
        observation_id=value.observation_id,
        evaluated_at=value.evaluated_at,
        ledger=evidence.confidence_ledger,
    )

    return LiveMarketCandidateEvaluationResultV1(
        observation,
        options,
        evidence,
        composition,
        composition_policy,
        candidate,
        action,
    )


def evaluate_live_market_candidate(
    value: LiveMarketCandidateEvaluationInputV1,
) -> LiveMarketCandidateEvaluationResultV1:
    """Existing fixed-policy evaluation path."""
    observation, options, evidence = (
        _build_live_candidate_base_evidence(value)
    )

    return _finalize_live_market_candidate(
        value=value,
        observation=observation,
        options=options,
        evidence=evidence,
        policy=value.policy,
    )


def evaluate_live_market_candidate_with_policy_factory(
    value: LiveMarketCandidateEvaluationInputV1,
    *,
    policy_factory: Callable[
        [LiveCanonicalEvidenceResultV1],
        LiveCandidatePolicySourceV1,
    ],
) -> LiveMarketCandidateEvaluationResultV1:
    """Build canonical evidence once, then derive the policy from it."""
    if not callable(policy_factory):
        raise TypeError("policy_factory")

    try:
        observation, options, evidence = (
            _build_live_candidate_base_evidence(value)
        )
    except Exception as exc:
        if not hasattr(exc, "task9_failure_stage"):
            setattr(
                exc,
                "task9_failure_stage",
                "TASK9_BASE_EVIDENCE",
            )
        raise

    try:
        policy = policy_factory(evidence)
    except Exception as exc:
        if not hasattr(exc, "task9_failure_stage"):
            setattr(
                exc,
                "task9_failure_stage",
                "TASK9_CANONICAL_POLICY",
            )
        raise

    try:
        return _finalize_live_market_candidate(
            value=value,
            observation=observation,
            options=options,
            evidence=evidence,
            policy=policy,
        )
    except Exception as exc:
        if not hasattr(exc, "task9_failure_stage"):
            setattr(
                exc,
                "task9_failure_stage",
                "TASK9_CANDIDATE_FINALIZATION",
            )
        raise


def evaluate_captured_certified_market_candidate(
    *,
    captured_evidence: CertifiedLiveCapturedEvidenceV1,
    session_validation: MarketSessionValidationV1,
    policy_source: LiveCandidatePolicySourceV1,
    parent_cycle_id: str,
    candidate_id: str,
    observation_id: str,
    engines: LiveCanonicalEvidenceEnginesV1,
    broader_market: BroaderMarketIntelligenceResultV1 | None = None,
    external_context: ExternalMarketContextResultV1 | None = None,
) -> LiveMarketCandidateEvaluationResultV1:
    """Pure one-market bridge from certified immutable capture."""
    if (
        type(captured_evidence)
        is not CertifiedLiveCapturedEvidenceV1
        or type(session_validation)
        is not MarketSessionValidationV1
        or type(policy_source)
        is not LiveCandidatePolicySourceV1
        or type(engines)
        is not LiveCanonicalEvidenceEnginesV1
    ):
        raise TypeError(
            "exact captured evaluator inputs"
        )

    spec = market_spec_for(
        captured_evidence.underlying_symbol,
        captured_evidence.spot_exchange,
    )

    if (
        session_validation.symbol,
        session_validation.exchange,
    ) != (
        spec.underlying_symbol,
        spec.exchange,
    ):
        raise ValueError("session identity")

    payload = dict(
        captured_evidence.spot_payload
    )

    if "data" not in payload:
        payload = {
            "data": {
                "ltp": payload.get(
                    "spot_price",
                    payload.get("ltp"),
                ),
                "tradingsymbol": (
                    spec.underlying_symbol
                ),
                "exchange": spec.exchange,
                "symboltoken": spec.symboltoken,
            }
        }

    value = LiveMarketCandidateEvaluationInputV1(
        spec,
        parent_cycle_id,
        candidate_id,
        observation_id,
        payload,
        captured_evidence.candle_rows_by_timeframe,
        captured_evidence.option_contracts,
        captured_evidence.option_chain_evidence_contracts,
        captured_evidence.provider_timestamp,
        captured_evidence.evaluated_at,
        session_validation,
        policy_source,
        engines,
        broader_market=broader_market,
        external_context=external_context,
        blockers=(
            captured_evidence.provider_blockers
        ),
        warnings=(
            captured_evidence.provider_warnings
        ),
    )

    return evaluate_live_market_candidate(
        value
    )


def evaluate_captured_certified_market_candidate_with_policy_factory(
    *,
    captured_evidence: CertifiedLiveCapturedEvidenceV1,
    session_validation: MarketSessionValidationV1,
    policy_factory: Callable[
        [LiveCanonicalEvidenceResultV1],
        LiveCandidatePolicySourceV1,
    ],
    parent_cycle_id: str,
    candidate_id: str,
    observation_id: str,
    engines: LiveCanonicalEvidenceEnginesV1,
    broader_market: BroaderMarketIntelligenceResultV1 | None = None,
    external_context: ExternalMarketContextResultV1 | None = None,
) -> LiveMarketCandidateEvaluationResultV1:
    """Captured-evidence path where policy is derived from canonical evidence."""
    if (
        type(captured_evidence)
        is not CertifiedLiveCapturedEvidenceV1
        or type(session_validation)
        is not MarketSessionValidationV1
        or type(engines)
        is not LiveCanonicalEvidenceEnginesV1
        or not callable(policy_factory)
    ):
        raise TypeError(
            "exact captured policy-factory inputs"
        )

    spec = market_spec_for(
        captured_evidence.underlying_symbol,
        captured_evidence.spot_exchange,
    )

    if (
        session_validation.symbol,
        session_validation.exchange,
    ) != (
        spec.underlying_symbol,
        spec.exchange,
    ):
        raise ValueError("session identity")

    payload = dict(
        captured_evidence.spot_payload
    )

    if "data" not in payload:
        payload = {
            "data": {
                "ltp": payload.get(
                    "spot_price",
                    payload.get("ltp"),
                ),
                "tradingsymbol": (
                    spec.underlying_symbol
                ),
                "exchange": spec.exchange,
                "symboltoken": spec.symboltoken,
            }
        }

    # The placeholder policy exists only to satisfy the immutable input
    # contract. It is never used as authority; policy_factory replaces it
    # after canonical evidence is built.
    placeholder = (
        LiveCandidatePolicySourceV1.unavailable(
            blockers=(
                "CANONICAL_POLICY_PENDING",
            )
        )
    )

    value = LiveMarketCandidateEvaluationInputV1(
        spec,
        parent_cycle_id,
        candidate_id,
        observation_id,
        payload,
        captured_evidence.candle_rows_by_timeframe,
        captured_evidence.option_contracts,
        captured_evidence.option_chain_evidence_contracts,
        captured_evidence.provider_timestamp,
        captured_evidence.evaluated_at,
        session_validation,
        placeholder,
        engines,
        broader_market=broader_market,
        external_context=external_context,
        blockers=(
            captured_evidence.provider_blockers
        ),
        warnings=(
            captured_evidence.provider_warnings
        ),
    )

    return (
        evaluate_live_market_candidate_with_policy_factory(
            value,
            policy_factory=policy_factory,
        )
    )


def attach_certified_candidate_evidence(raw_analysis:Mapping[str,object],evaluation:LiveMarketCandidateEvaluationResultV1)->dict[str,object]:
 if not isinstance(raw_analysis,Mapping) or type(evaluation) is not LiveMarketCandidateEvaluationResultV1:raise TypeError("attachment")
 value=dict(raw_analysis);value.update({"certified_candidate_composition":evaluation.composition,"certified_candidate_policy":evaluation.policy,"certified_market_candidate":evaluation.candidate,"certified_blockers":evaluation.policy.blockers,"certified_warnings":evaluation.policy.warnings,"certified_reasons":evaluation.policy.reasons,"certified_invalidation_conditions":evaluation.policy.invalidation_conditions});return value

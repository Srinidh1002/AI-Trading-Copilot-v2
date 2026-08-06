"""Strict Task 8 bridge from captured live evidence to typed candidates.

This module performs no provider reads and introduces no alternative
intelligence calculations. It either:

1. evaluates the already captured immutable live evidence through the existing
   canonical engines and returns the complete typed evaluation, or
2. composes an already supplied exact candidate composition and policy.

The CandidateReader-compatible adapter continues to return only the exact
MarketAnalysisCandidateV1.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace

from services.analysis.live_canonical_engine_adapters import (
    build_default_live_canonical_evidence_engines,
)
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    LiveMarketCandidateEvaluationResultV1,
    evaluate_captured_certified_market_candidate,
)
from services.analysis.market_analysis_candidate_composer import (
    MarketAnalysisCandidateCompositionInputV1,
    MarketAnalysisCandidateCompositionPolicyV1,
    compose_market_analysis_candidate,
)
from services.contracts.certified_live_captured_evidence_v1 import (
    CertifiedLiveCapturedEvidenceV1,
)
from services.contracts.certified_shared_market_context_v1 import (
    CertifiedSharedMarketContextV1,
)
from services.contracts.market_analysis_candidate_v1 import (
    MarketAnalysisCandidateV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.paper_orchestration.certified_live_read_authorities import (
    CertifiedLiveDataResultV1,
)


_SUPPORTED_MARKETS = {
    ("NIFTY", "NSE"),
    ("SENSEX", "BSE"),
}


def _validate_common_inputs(
    *,
    cycle_input: PaperOrchestrationCycleInputV1,
    data_result: CertifiedLiveDataResultV1,
    supplied_analysis: Mapping[str, object],
    captured_evidence: CertifiedLiveCapturedEvidenceV1 | None,
    shared_context: CertifiedSharedMarketContextV1 | None,
    parent_cycle_id: str,
) -> tuple[str, str]:
    if type(cycle_input) is not PaperOrchestrationCycleInputV1:
        raise TypeError("cycle_input")
    if type(data_result) is not CertifiedLiveDataResultV1:
        raise TypeError("data_result")
    if not isinstance(supplied_analysis, Mapping):
        raise TypeError("supplied_analysis")
    if (
        captured_evidence is not None
        and type(captured_evidence) is not CertifiedLiveCapturedEvidenceV1
    ):
        raise TypeError("captured_evidence")
    if (
        shared_context is not None
        and type(shared_context) is not CertifiedSharedMarketContextV1
    ):
        raise TypeError("shared_context")
    if type(parent_cycle_id) is not str or not parent_cycle_id.strip():
        raise ValueError("parent_cycle_id")

    expected = (
        cycle_input.underlying_symbol,
        cycle_input.exchange,
    )
    if expected not in _SUPPORTED_MARKETS:
        raise ValueError("unsupported Task 8 market")

    data_identity = (
        data_result.underlying_symbol,
        data_result.exchange,
    )
    if data_identity != expected:
        raise ValueError("data identity mismatch")


    if data_result.market_timestamp != cycle_input.market_timestamp:
        raise ValueError("data timestamp identity mismatch")

    if captured_evidence is not None:
        captured_identity = (
            captured_evidence.underlying_symbol,
            captured_evidence.spot_exchange,
            captured_evidence.spot_token,
        )
        expected_captured_identity = (
            cycle_input.underlying_symbol,
            cycle_input.exchange,
            data_result.symboltoken,
        )
        if captured_identity != expected_captured_identity:
            raise ValueError("captured evidence identity mismatch")

    if (
        shared_context is not None
        and shared_context.shared_external_context is not None
    ):
        external = shared_context.shared_external_context
        if (
            external.cycle_id != shared_context.cycle_id
            or external.evaluated_at != shared_context.evaluated_at
        ):
            raise ValueError("shared external context cycle")

    return expected


def _policy_source(
    supplied_analysis: Mapping[str, object],
) -> LiveCandidatePolicySourceV1:
    direction = supplied_analysis.get("policy_direction")
    eligibility = supplied_analysis.get("policy_eligibility")
    confidence = supplied_analysis.get("policy_confidence")
    score = supplied_analysis.get("policy_score")

    if not all(
        value is not None
        for value in (
            direction,
            eligibility,
            confidence,
            score,
        )
    ):
        return LiveCandidatePolicySourceV1.unavailable()

    return LiveCandidatePolicySourceV1(
        direction=direction,
        eligibility=eligibility,
        confidence=confidence,
        score=score,
        reasons=tuple(
            supplied_analysis.get(
                "policy_reasons",
                (),
            )
        ),
        invalidation_conditions=tuple(
            supplied_analysis.get(
                "policy_invalidation_conditions",
                (),
            )
        ),
        blockers=tuple(
            supplied_analysis.get(
                "policy_blockers",
                (),
            )
        ),
        warnings=tuple(
            supplied_analysis.get(
                "policy_warnings",
                (),
            )
        ),
        contradictions=tuple(
            supplied_analysis.get(
                "policy_contradictions",
                (),
            )
        ),
    )


def evaluate_task8_live_candidate(
    cycle_input: PaperOrchestrationCycleInputV1,
    data_result: CertifiedLiveDataResultV1,
    supplied_analysis: Mapping[str, object],
    captured_evidence: CertifiedLiveCapturedEvidenceV1,
    shared_context: CertifiedSharedMarketContextV1 | None = None,
    *,
    parent_cycle_id: str,
) -> LiveMarketCandidateEvaluationResultV1:
    """Return the complete provider-free Task 8 typed evaluation.

    The supplied captured evidence is evaluated once through the existing
    canonical evidence engines. No quote, candle, option-chain, news, context,
    broker, or execution provider is called here.
    """

    expected = _validate_common_inputs(
        cycle_input=cycle_input,
        data_result=data_result,
        supplied_analysis=supplied_analysis,
        captured_evidence=captured_evidence,
        shared_context=shared_context,
        parent_cycle_id=parent_cycle_id,
    )

    evaluation_capture = captured_evidence
    broader_market = None
    external_context = None

    if shared_context is not None:
        evaluation_capture = replace(
            captured_evidence,
            evaluated_at=shared_context.evaluated_at,
        )
        broader_market = shared_context.for_market(*expected)

        if shared_context.shared_external_context is not None:
            external_context = (
                shared_context.shared_external_context.for_market(
                    *expected
                )
            )

    result = evaluate_captured_certified_market_candidate(
        captured_evidence=evaluation_capture,
        session_validation=cycle_input.session_validation,
        policy_source=_policy_source(supplied_analysis),
        parent_cycle_id=parent_cycle_id,
        candidate_id=(
            f"certified-live:{cycle_input.observation_id}"
        ),
        observation_id=cycle_input.observation_id,
        engines=build_default_live_canonical_evidence_engines(),
        broader_market=broader_market,
        external_context=external_context,
    )
    if type(result) is not LiveMarketCandidateEvaluationResultV1:
        raise TypeError(
            "candidate evaluator must return exact "
            "LiveMarketCandidateEvaluationResultV1"
        )

    candidate = result.candidate
    candidate_identity = (
        candidate.underlying_symbol,
        candidate.exchange,
        candidate.symboltoken,
        candidate.observation_id,
    )
    expected_identity = (
        cycle_input.underlying_symbol,
        cycle_input.exchange,
        data_result.symboltoken,
        cycle_input.observation_id,
    )
    if candidate_identity != expected_identity:
        raise ValueError("evaluated candidate identity mismatch")
    if candidate.market_timestamp != data_result.market_timestamp:
        raise ValueError("evaluated candidate timestamp mismatch")

    normalized_candidate = replace(
        candidate,
        requested_at=cycle_input.cycle_requested_at,
    )
    return replace(
        result,
        candidate=normalized_candidate,
    )


def adapt_task8_live_candidate(
    cycle_input: PaperOrchestrationCycleInputV1,
    data_result: CertifiedLiveDataResultV1,
    supplied_analysis: Mapping[str, object],
    captured_evidence: CertifiedLiveCapturedEvidenceV1 | None = None,
    shared_context: CertifiedSharedMarketContextV1 | None = None,
    *,
    parent_cycle_id: str,
) -> MarketAnalysisCandidateV1:
    """CandidateReader-compatible Task 8 adapter.

    Captured live evidence uses ``evaluate_task8_live_candidate``. Exact
    pre-composed candidate inputs remain supported for compatibility.
    """

    expected = _validate_common_inputs(
        cycle_input=cycle_input,
        data_result=data_result,
        supplied_analysis=supplied_analysis,
        captured_evidence=captured_evidence,
        shared_context=shared_context,
        parent_cycle_id=parent_cycle_id,
    )

    composition = supplied_analysis.get(
        "certified_candidate_composition"
    )
    policy = supplied_analysis.get(
        "certified_candidate_policy"
    )

    if (
        captured_evidence is not None
        and composition is None
        and policy is None
    ):
        return evaluate_task8_live_candidate(
            cycle_input,
            data_result,
            supplied_analysis,
            captured_evidence,
            shared_context,
            parent_cycle_id=parent_cycle_id,
        ).candidate

    if type(composition) is not MarketAnalysisCandidateCompositionInputV1:
        raise TypeError("certified_candidate_composition")
    if type(policy) is not MarketAnalysisCandidateCompositionPolicyV1:
        raise TypeError("certified_candidate_policy")

    composition_identity = (
        composition.underlying_symbol,
        composition.exchange,
    )
    if composition_identity != expected:
        raise ValueError(
            "candidate composition identity mismatch"
        )
    if composition.symboltoken != data_result.symboltoken:
        raise ValueError(
            "candidate composition symboltoken mismatch"
        )
    if composition.observation_id != cycle_input.observation_id:
        raise ValueError(
            "candidate composition observation mismatch"
        )
    if composition.market_timestamp != data_result.market_timestamp:
        raise ValueError(
            "candidate composition timestamp mismatch"
        )
    if composition.requested_at != cycle_input.cycle_requested_at:
        raise ValueError(
            "candidate composition requested timestamp mismatch"
        )
    if composition.received_at != cycle_input.received_at:
        raise ValueError(
            "candidate composition receipt timestamp mismatch"
        )

    candidate = compose_market_analysis_candidate(
        composition,
        policy,
    )
    if type(candidate) is not MarketAnalysisCandidateV1:
        raise TypeError("candidate composer result")

    return candidate



Task8EvaluationSink = Callable[
    [str, LiveMarketCandidateEvaluationResultV1],
    None,
]


def build_task8_retaining_candidate_reader(
    *,
    evaluation_sink: Task8EvaluationSink,
):
    """Build a CandidateReader that retains each exact typed evaluation once.

    The returned reader preserves the generic CandidateReader contract by
    returning only ``MarketAnalysisCandidateV1``. The sink receives the exact
    ``LiveMarketCandidateEvaluationResultV1`` keyed by observation identity.

    No provider is reread and the canonical evaluator is invoked exactly once
    for each captured-evidence candidate call.
    """

    if not callable(evaluation_sink):
        raise TypeError("evaluation_sink must be callable")

    def reader(
        cycle_input: PaperOrchestrationCycleInputV1,
        data_result: CertifiedLiveDataResultV1,
        supplied_analysis: Mapping[str, object],
        captured_evidence: CertifiedLiveCapturedEvidenceV1 | None = None,
        shared_context: CertifiedSharedMarketContextV1 | None = None,
        *,
        parent_cycle_id: str,
    ) -> MarketAnalysisCandidateV1:
        composition = supplied_analysis.get(
            "certified_candidate_composition"
        )
        policy = supplied_analysis.get(
            "certified_candidate_policy"
        )

        if (
            captured_evidence is not None
            and composition is None
            and policy is None
        ):
            evaluation = evaluate_task8_live_candidate(
                cycle_input,
                data_result,
                supplied_analysis,
                captured_evidence,
                shared_context,
                parent_cycle_id=parent_cycle_id,
            )
            evaluation_sink(
                cycle_input.observation_id,
                evaluation,
            )
            return evaluation.candidate

        return adapt_task8_live_candidate(
            cycle_input,
            data_result,
            supplied_analysis,
            captured_evidence,
            shared_context,
            parent_cycle_id=parent_cycle_id,
        )

    return reader

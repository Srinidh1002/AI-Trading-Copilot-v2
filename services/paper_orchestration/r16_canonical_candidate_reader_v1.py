"""R16 canonical candidate reader for the exact-two-index SHADOW parent.

This adapter turns already-captured immutable NIFTY/SENSEX evidence into the
repository's canonical MarketAnalysisCandidateV1.  It performs no provider
reads and has no P6/P7/P8 or broker authority.
"""
from __future__ import annotations

from dataclasses import replace

from services.analysis.canonical_directional_policy_evaluator import (
    evaluate_canonical_directional_policy,
)
from services.analysis.canonical_evidence_family_adapters import (
    broader_market_family,
    derivatives_family,
    external_context_family,
    regime_family,
    technical_family,
)
from services.analysis.live_canonical_engine_adapters import (
    build_default_live_canonical_evidence_engines,
)
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    evaluate_captured_certified_market_candidate_with_policy_factory,
)
from services.contracts.canonical_evidence_family_v1 import (
    CanonicalEvidenceFamilySetV1,
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


def _unique(values) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(value).strip()
            for value in values
            if str(value).strip()
        )
    )


def _canonical_policy_source(
    *,
    evidence,
    parent_cycle_id: str,
) -> LiveCandidatePolicySourceV1:
    """Derive one candidate policy from canonical family evidence only."""

    contributions = [
        technical_family(evidence.technical),
        derivatives_family(evidence.option_chain),
        regime_family(evidence.regime),
    ]

    if evidence.broader_market is not None:
        contributions.append(
            broader_market_family(evidence.broader_market)
        )

    if evidence.external_context is not None:
        contributions.append(
            external_context_family(evidence.external_context)
        )

    family_set = CanonicalEvidenceFamilySetV1(
        tuple(contributions)
    )

    canonical = evaluate_canonical_directional_policy(
        policy_id=(
            f"{parent_cycle_id}:canonical:"
            f"{evidence.observation.spot.underlying_symbol.lower()}"
        ),
        symbol=evidence.observation.spot.underlying_symbol,
        exchange=evidence.observation.spot.exchange,
        evaluated_at=evidence.regime.created_at,
        evidence=family_set,
    )

    if canonical.decision == "TRADE":
        eligibility = "ELIGIBLE"
    elif canonical.direction == "UNAVAILABLE":
        eligibility = "UNAVAILABLE"
    else:
        eligibility = "INELIGIBLE"

    return LiveCandidatePolicySourceV1(
        direction=canonical.direction,
        eligibility=eligibility,
        confidence=canonical.confidence,
        score=canonical.score,
        reasons=_unique(canonical.reasons),
        invalidation_conditions=(),
        blockers=_unique(
            (
                *canonical.blockers,
                *canonical.entry_restrictions,
            )
        ),
        warnings=_unique(canonical.warnings),
        contradictions=_unique(canonical.contradictions),
    )


class R16CanonicalCandidateReaderV1:
    """Provider-free candidate reader over supplied immutable captures."""

    execution_mode = "PAPER"
    live_execution_eligible = False
    broker_order_submission = False
    mode = "SHADOW_ONLY"

    def __init__(self, *, engines=None) -> None:
        self.engines = (
            engines
            if engines is not None
            else build_default_live_canonical_evidence_engines()
        )

    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
        data_result: CertifiedLiveDataResultV1,
        analysis,
        captured_evidence: CertifiedLiveCapturedEvidenceV1 | None,
        shared_context: CertifiedSharedMarketContextV1 | None,
        *,
        parent_cycle_id: str,
    ) -> MarketAnalysisCandidateV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError("cycle_input")
        if type(data_result) is not CertifiedLiveDataResultV1:
            raise TypeError("data_result")
        if captured_evidence is None:
            raise RuntimeError("CANONICAL_CAPTURE_REQUIRED")
        if type(captured_evidence) is not CertifiedLiveCapturedEvidenceV1:
            raise TypeError("captured_evidence")
        if shared_context is not None and type(shared_context) is not CertifiedSharedMarketContextV1:
            raise TypeError("shared_context")
        if type(parent_cycle_id) is not str or not parent_cycle_id.strip():
            raise ValueError("parent_cycle_id")

        identity = (
            cycle_input.underlying_symbol,
            cycle_input.exchange,
        )
        captured_identity = (
            captured_evidence.underlying_symbol,
            captured_evidence.spot_exchange,
        )
        if captured_identity != identity:
            raise ValueError("captured evidence identity")
        if (
            data_result.observation_id != cycle_input.observation_id
            or data_result.underlying_symbol != identity[0]
            or data_result.exchange != identity[1]
            or data_result.market_timestamp != cycle_input.market_timestamp
        ):
            raise ValueError("data/cycle identity")

        broader = None
        external = None
        evaluation_boundary = captured_evidence.evaluated_at

        if shared_context is not None:
            broader = shared_context.for_market(*identity)
            evaluation_boundary = max(
                evaluation_boundary,
                shared_context.evaluated_at,
            )
            if shared_context.shared_external_context is not None:
                external = (
                    shared_context
                    .shared_external_context
                    .for_market(*identity)
                )

        # Re-evaluate the immutable captured payload at the coherent parent
        # boundary.  The underlying provider timestamp remains unchanged.
        captured_at_parent = replace(
            captured_evidence,
            evaluated_at=evaluation_boundary,
        )

        evaluation = (
            evaluate_captured_certified_market_candidate_with_policy_factory(
                captured_evidence=captured_at_parent,
                session_validation=cycle_input.session_validation,
                policy_factory=lambda evidence: _canonical_policy_source(
                    evidence=evidence,
                    parent_cycle_id=parent_cycle_id,
                ),
                parent_cycle_id=parent_cycle_id,
                candidate_id=(
                    f"{parent_cycle_id}:candidate:"
                    f"{identity[0].lower()}"
                ),
                observation_id=cycle_input.observation_id,
                engines=self.engines,
                broader_market=broader,
                external_context=external,
            )
        )

        candidate = evaluation.candidate
        if type(candidate) is not MarketAnalysisCandidateV1:
            raise TypeError("canonical candidate result")

        # This adapter is intentionally observational.  These invariants make
        # accidental promotion to order authority fail code review/tests.
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.mode != "SHADOW_ONLY"
        ):
            raise RuntimeError("R16_SHADOW_SAFETY_INVARIANT")

        return candidate


def install_r16_canonical_candidate_reader(
    readers,
    *,
    engines=None,
):
    """Return a new CertifiedLiveProviderReaders with the R16 reader installed.

    Runtime caches are deliberately not copied.  This builder is intended for a
    fresh shadow composition, not for mutating a running reader instance.
    """

    from services.paper_orchestration.certified_live_provider_readers import (
        CertifiedLiveProviderReaders,
    )

    if type(readers) is not CertifiedLiveProviderReaders:
        raise TypeError("readers")

    return CertifiedLiveProviderReaders(
        quote_reader=readers.quote_reader,
        analysis_pipeline=readers.analysis_pipeline,
        option_decision_pipeline=readers.option_decision_pipeline,
        available_capital=readers.available_capital,
        candidate_reader=R16CanonicalCandidateReaderV1(
            engines=engines,
        ),
        capture_reader=readers.capture_reader,
        india_vix_reader=readers.india_vix_reader,
        external_context_reader=readers.external_context_reader,
        substage_callback=readers.substage_callback,
        risk_percent=readers.risk_percent,
        maximum_capital_usage_percent=(
            readers.maximum_capital_usage_percent
        ),
    )

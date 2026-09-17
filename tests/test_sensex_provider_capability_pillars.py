from dataclasses import replace

from services.analysis.live_canonical_engine_adapters import (
    build_default_live_canonical_evidence_engines,
)
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    evaluate_captured_certified_market_candidate,
)
from services.analysis.market_analysis_candidate_composer import (
    MarketAnalysisCandidateCompositionPolicyV1,
    compose_market_analysis_candidate,
)
from services.contracts.market_analysis_candidate_v1 import (
    MarketAnalysisEvidenceV1,
)
from services.market_session.validator import (
    validate_session_timestamp,
)
from tests.test_task8_parent_typed_candidate_certification import (
    NOW,
    captured,
)
from services.analysis.live_typed_candidate_evidence import (
    LiveTypedEvidenceInputV1,
    compose_from_live_canonical_evidence,
)
from services.analysis.market_analysis_pillar_aggregation import (
    aggregate_market_analysis_pillars,
)

def _evaluate(symbol, exchange, spot):
    source = captured(
        symbol,
        exchange,
        spot,
        complete_options=True,
    )

    session = validate_session_timestamp(
        symbol=symbol,
        exchange=exchange,
        market_timestamp=NOW,
        evaluated_at=NOW,
        validation_mode="LENIENT_ANALYSIS",
        id_factory=lambda: (
            f"provider-capability:{symbol}"
        ),
    )

    return evaluate_captured_certified_market_candidate(
        captured_evidence=source,
        session_validation=session,
        policy_source=LiveCandidatePolicySourceV1(
            "BULLISH",
            "ELIGIBLE",
            80.0,
            80.0,
        ),
        parent_cycle_id=(
            f"provider-capability-parent:{symbol}"
        ),
        candidate_id=(
            f"provider-capability-candidate:{symbol}"
        ),
        observation_id=(
            f"provider-capability-observation:{symbol}"
        ),
        engines=(
            build_default_live_canonical_evidence_engines()
        ),
    )


def test_sensex_provider_unsupported_greeks_do_not_hard_block():
    result = _evaluate(
        "SENSEX",
        "BSE",
        80000.0,
    )

    assert result.composition.greeks.status == "UNAVAILABLE"

    assert (
        "EVIDENCE_UNAVAILABLE_GREEKS"
        not in result.candidate.blockers
    )

    assert (
        "OPTION_GREEKS_PROVIDER_CAPABILITY_UNAVAILABLE"
        in result.candidate.warnings
    )

    assert "REGIME_BLOCKED" in result.candidate.blockers


def test_nifty_missing_greeks_remain_hard_required():
    result = _evaluate(
        "NIFTY",
        "NSE",
        25000.0,
    )

    assert result.composition.greeks.status == "UNAVAILABLE"

    assert (
        "EVIDENCE_UNAVAILABLE_GREEKS"
        in result.candidate.blockers
    )


def test_sensex_provider_unsupported_iv_is_nonblocking_but_retained():
    result = _evaluate(
        "SENSEX",
        "BSE",
        80000.0,
    )

    unavailable_iv = MarketAnalysisEvidenceV1(
        status="UNAVAILABLE",
        provenance={
            "source": "canonical_option_chain_metric",
            "metrics": ("IV_SKEW",),
        },
        summary={
            "metric_statuses": {
                "IV_SKEW": "UNAVAILABLE",
            },
        },
    )

    composition = replace(
        result.composition,
        iv=unavailable_iv,
    )

    candidate = compose_market_analysis_candidate(
        composition,
        MarketAnalysisCandidateCompositionPolicyV1(
            direction="BULLISH",
            eligibility="ELIGIBLE",
            confidence=80.0,
            score=80.0,
        ),
    )

    assert candidate.iv.status == "UNAVAILABLE"

    assert (
        "EVIDENCE_UNAVAILABLE_IV"
        not in candidate.blockers
    )

    assert (
        "OPTION_IV_PROVIDER_CAPABILITY_UNAVAILABLE"
        in candidate.warnings
    )


def test_sensex_unrelated_unavailable_pillar_still_blocks():
    result = _evaluate(
        "SENSEX",
        "BSE",
        80000.0,
    )

    unavailable_oi = MarketAnalysisEvidenceV1(
        status="UNAVAILABLE",
        provenance={
            "source": "canonical_option_chain_metric",
            "metrics": ("OI_CONCENTRATION",),
        },
        summary={
            "metric_statuses": {
                "OI_CONCENTRATION": "UNAVAILABLE",
            },
        },
    )

    composition = replace(
        result.composition,
        oi=unavailable_oi,
    )

    candidate = compose_market_analysis_candidate(
        composition,
        MarketAnalysisCandidateCompositionPolicyV1(
            direction="BULLISH",
            eligibility="ELIGIBLE",
            confidence=80.0,
            score=80.0,
        ),
    )

    assert (
        "EVIDENCE_UNAVAILABLE_OI"
        in candidate.blockers
    )
def _recompose_with_unavailable_iv(result):
    unavailable_iv = MarketAnalysisEvidenceV1(
        status="UNAVAILABLE",
        provenance={
            "source": "canonical_option_chain_metric",
            "metrics": ("IV_SKEW",),
        },
        summary={
            "metric_statuses": {
                "IV_SKEW": "UNAVAILABLE",
            },
            "metric_values": {
                "IV_SKEW": None,
            },
            "metric_signals": {
                "IV_SKEW": "UNAVAILABLE",
            },
            "blockers": (
                "implied volatility is unavailable for all quotes",
            ),
            "warnings": (),
        },
    )

    pillars = dict(
        result.evidence.pillars.ordered_pillars
    )
    pillars["iv"] = unavailable_iv

    aggregate = aggregate_market_analysis_pillars(
        pillars=pillars,
        evaluated_at=result.evidence.pillars.evaluated_at,
    )

    evidence = replace(
        result.evidence,
        pillars=aggregate,
    )

    composition = result.composition

    source = LiveTypedEvidenceInputV1(
        candidate_id=composition.candidate_id,
        observation_id=composition.observation_id,
        underlying_symbol=composition.underlying_symbol,
        exchange=composition.exchange,
        option_exchange=composition.option_exchange,
        symboltoken=composition.symboltoken,
        requested_at=composition.requested_at,
        market_timestamp=composition.market_timestamp,
        received_at=composition.received_at,
        normalized_market=result.observation,
        normalized_options=result.options,
        session=evidence.session,
        direction="BULLISH",
        eligibility="ELIGIBLE",
        confidence=80.0,
        score=80.0,
    )

    recomposed, policy = compose_from_live_canonical_evidence(
        source=source,
        evidence=evidence,
    )

    candidate = compose_market_analysis_candidate(
        recomposed,
        policy,
    )

    return evidence, recomposed, policy, candidate


def test_sensex_live_handoff_exempts_only_provider_unsupported_iv_blocker():
    result = _evaluate(
        "SENSEX",
        "BSE",
        80000.0,
    )

    evidence, composition, policy, candidate = (
        _recompose_with_unavailable_iv(result)
    )

    assert composition.iv.status == "UNAVAILABLE"

    # Prove the pre-handoff aggregate really contains the live blocker.
    assert (
        "implied volatility is unavailable for all quotes"
        in evidence.pillars.blockers
    )

    # Task 9.78 repair: BFO unsupported IV does not survive as
    # a universal policy/candidate blocker.
    assert (
        "implied volatility is unavailable for all quotes"
        not in policy.blockers
    )

    assert (
        "implied volatility is unavailable for all quotes"
        not in candidate.blockers
    )

    assert (
        "EVIDENCE_UNAVAILABLE_IV"
        not in candidate.blockers
    )

    assert (
        "OPTION_IV_PROVIDER_CAPABILITY_UNAVAILABLE"
        in candidate.warnings
    )

    # The evidence remains immutable/auditable rather than fabricated.
    assert evidence.pillars.ordered_pillars["iv"].status == "UNAVAILABLE"
    assert (
        evidence.pillars.ordered_pillars["iv"].summary["blockers"]
        == (
            "implied volatility is unavailable for all quotes",
        )
    )


def test_nifty_live_handoff_preserves_same_iv_blocker_fail_closed():
    result = _evaluate(
        "NIFTY",
        "NSE",
        25000.0,
    )

    evidence, composition, policy, candidate = (
        _recompose_with_unavailable_iv(result)
    )

    assert composition.iv.status == "UNAVAILABLE"

    assert (
        "implied volatility is unavailable for all quotes"
        in evidence.pillars.blockers
    )

    # NFO has no BFO capability exemption.
    assert (
        "implied volatility is unavailable for all quotes"
        in policy.blockers
    )

    assert (
        "implied volatility is unavailable for all quotes"
        in candidate.blockers
    )

    assert (
        "EVIDENCE_UNAVAILABLE_IV"
        in candidate.blockers
    )

    assert (
        "OPTION_IV_PROVIDER_CAPABILITY_UNAVAILABLE"
        not in candidate.warnings
    )

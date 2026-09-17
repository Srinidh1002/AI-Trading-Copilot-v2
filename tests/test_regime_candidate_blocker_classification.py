from tests.test_task8_parent_typed_candidate_certification import (
    NOW,
    captured,
)

from services.analysis.live_canonical_engine_adapters import (
    build_default_live_canonical_evidence_engines,
)
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    evaluate_captured_certified_market_candidate,
)
from services.market_session.validator import (
    validate_session_timestamp,
)


def _evaluate():
    source = captured(
        "NIFTY",
        "NSE",
        25000.0,
        complete_options=True,
    )

    session = validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=NOW,
        evaluated_at=NOW,
        validation_mode="LENIENT_ANALYSIS",
        id_factory=lambda: (
            "regime-blocker-classification-session"
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
            "regime-blocker-classification-parent"
        ),
        candidate_id=(
            "regime-blocker-classification-candidate"
        ),
        observation_id=(
            "regime-blocker-classification-observation"
        ),
        engines=(
            build_default_live_canonical_evidence_engines()
        ),
    )


def test_valid_not_suitable_regime_is_not_reported_unavailable():
    result = _evaluate()
    regime = result.evidence.regime

    assert regime.context_status in {
        "READY",
        "READY_WITH_WARNINGS",
    }
    assert regime.entry_suitability == "NOT_SUITABLE"
    assert not regime.blockers
    assert not regime.contradictions

    assert "REGIME_BLOCKED" in (
        result.candidate.blockers
    )

    assert "EVIDENCE_UNAVAILABLE_REGIME" not in (
        result.candidate.blockers
    )


def test_confidence_ledger_uses_same_regime_classification():
    result = _evaluate()

    assert "REGIME_BLOCKED" in (
        result.evidence.confidence_ledger.blockers
    )

    assert "EVIDENCE_UNAVAILABLE_REGIME" not in (
        result.evidence.confidence_ledger.blockers
    )


def test_regime_block_does_not_enable_trade():
    result = _evaluate()

    assert result.candidate.eligibility == "UNAVAILABLE"
    assert result.candidate.confidence == 0.0
    assert result.candidate.score == 0.0

    assert result.pre_entry_action.action == "NO_TRADE"
    assert "REGIME_BLOCKED" in result.pre_entry_action.blockers

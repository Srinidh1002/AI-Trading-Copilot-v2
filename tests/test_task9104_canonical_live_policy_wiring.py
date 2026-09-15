from services.analysis.live_canonical_engine_adapters import (
    build_default_live_canonical_evidence_engines,
)
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    evaluate_captured_certified_market_candidate_with_policy_factory,
)
from services.market_session.validator import (
    validate_session_timestamp,
)

from test_task8_parent_typed_candidate_certification import (
    NOW,
    captured,
)


def test_policy_factory_runs_after_exact_canonical_evidence_build():
    value = captured(
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
        id_factory=lambda: "session:task9104",
    )

    calls = []

    def policy_factory(evidence):
        calls.append(evidence)

        assert evidence.technical is not None
        assert evidence.regime is not None
        assert evidence.option_chain is not None
        assert evidence.contract_ranking is not None
        assert evidence.pillars is not None

        return LiveCandidatePolicySourceV1(
            direction="BULLISH",
            eligibility="INELIGIBLE",
            confidence=60.0,
            score=60.0,
            blockers=("TEST_GATE",),
        )

    result = (
        evaluate_captured_certified_market_candidate_with_policy_factory(
            captured_evidence=value,
            session_validation=session,
            policy_factory=policy_factory,
            parent_cycle_id="task9104-parent",
            candidate_id="task9104-candidate",
            observation_id="task9104-observation",
            engines=(
                build_default_live_canonical_evidence_engines()
            ),
        )
    )

    assert len(calls) == 1
    assert calls[0] is result.evidence or (
        calls[0].technical
        is result.evidence.technical
    )

    assert (
        "CANONICAL_POLICY_PENDING"
        not in result.candidate.blockers
    )

    assert (
        "CANONICAL_POLICY_UNAVAILABLE"
        not in result.candidate.blockers
    )


def test_task9_source_does_not_reenable_legacy_fallback():
    from pathlib import Path

    source = Path(
        "services/certification/"
        "task9_live_candidate_adapter.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "allow_legacy_fallback=True"
        not in source
    )

    assert (
        "evaluate_canonical_directional_policy"
        in source
    )

    assert (
        "CanonicalEvidenceFamilySetV1"
        in source
    )

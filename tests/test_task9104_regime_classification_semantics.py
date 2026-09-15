from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from services.analysis.pre_entry_action_resolver import (
    resolve_pre_entry_market_action,
)
from services.analysis.market_analysis_candidate_composer import (
    _required_failure_code,
)
from services.analysis.market_decision_explanation import (
    build_market_decision_explanation,
)

from test_market_analysis_candidate_v1 import build


NOW = datetime(
    2026,
    8,
    20,
    5,
    15,
    tzinfo=timezone.utc,
)


def _candidate_with_suitability(value):
    candidate = build(
        underlying_symbol="NIFTY",
        candidate_id=f"candidate:{value}",
        observation_id=f"observation:{value}",
        direction="UNAVAILABLE",
        eligibility="UNAVAILABLE",
        confidence=0.0,
        score=0.0,
        blockers=("TEST_NONREADY_CANDIDATE",),
    )

    return replace(
        candidate,
        regime=replace(
            candidate.regime,
            entry_suitability=value,
        ),
    )


def test_unavailable_regime_is_not_mislabeled_as_blocked():
    candidate = _candidate_with_suitability(
        "UNAVAILABLE"
    )

    action = resolve_pre_entry_market_action(
        candidate=candidate,
        cycle_id="cycle:unavailable",
        observation_id="observation:unavailable",
        evaluated_at=NOW,
    )

    assert action.action == "NO_TRADE"
    assert "EVIDENCE_UNAVAILABLE_REGIME" in action.blockers
    assert "REGIME_BLOCKED" not in action.blockers
    assert action.reasons == (
        "EVIDENCE_UNAVAILABLE_REGIME",
    )


def test_not_suitable_regime_remains_truthfully_blocked():
    candidate = _candidate_with_suitability(
        "NOT_SUITABLE"
    )

    action = resolve_pre_entry_market_action(
        candidate=candidate,
        cycle_id="cycle:not-suitable",
        observation_id="observation:not-suitable",
        evaluated_at=NOW,
    )

    assert action.action == "NO_TRADE"
    assert "REGIME_BLOCKED" in action.blockers
    assert action.reasons == (
        "REGIME_BLOCKED",
    )


def test_explanation_preserves_unavailable_regime_semantics():
    candidate = _candidate_with_suitability(
        "UNAVAILABLE"
    )

    action = resolve_pre_entry_market_action(
        candidate=candidate,
        cycle_id="cycle:explanation",
        observation_id="observation:explanation",
        evaluated_at=NOW,
    )

    explanation = build_market_decision_explanation(
        cycle_id="cycle:explanation",
        observation_id="observation:explanation",
        candidate=candidate,
        action=action,
        evaluated_at=NOW,
    )

    reasons = tuple(
        item.stable_reason_code
        for item in explanation.entries
    )

    assert "EVIDENCE_UNAVAILABLE_REGIME" in reasons
    assert "REGIME_CAUTION" not in reasons

def _available_regime(**overrides):
    values = {
        "context_status": "READY_WITH_WARNINGS",
        "primary_regime": "STRONG_BEARISH",
        "entry_suitability": "CAUTION",
        "entry_restriction_state": "OPEN",
        "analysis_allowed": True,
        "new_entries_allowed": True,
        "blockers": (),
        "contradictions": (),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_available_caution_regime_uses_policy_classification():
    assert (
        _required_failure_code(
            "regime",
            _available_regime(),
        )
        == "REGIME_CAUTION"
    )


def test_blocked_controls_override_caution_classification():
    assert (
        _required_failure_code(
            "regime",
            _available_regime(
                new_entries_allowed=False,
            ),
        )
        == "REGIME_BLOCKED"
    )


def test_caution_regime_remains_zero_confidence_no_trade():
    candidate = _candidate_with_suitability(
        "CAUTION"
    )
    candidate = replace(
        candidate,
        blockers=("REGIME_CAUTION",),
    )

    action = resolve_pre_entry_market_action(
        candidate=candidate,
        cycle_id="cycle:caution",
        observation_id="observation:caution",
        evaluated_at=NOW,
    )

    assert action.action == "NO_TRADE"
    assert action.candidate_direction == "UNAVAILABLE"
    assert action.confidence == 0.0
    assert action.score == 0.0
    assert action.reasons == ("REGIME_CAUTION",)
    assert "REGIME_CAUTION" in action.blockers
    assert "EVIDENCE_UNAVAILABLE_REGIME" not in action.blockers

    explanation = build_market_decision_explanation(
        cycle_id="cycle:caution",
        observation_id="observation:caution",
        candidate=candidate,
        action=action,
        evaluated_at=NOW,
    )

    reasons = tuple(
        item.stable_reason_code
        for item in explanation.entries
    )

    assert "REGIME_CAUTION" in reasons
    assert "EVIDENCE_UNAVAILABLE_REGIME" not in reasons


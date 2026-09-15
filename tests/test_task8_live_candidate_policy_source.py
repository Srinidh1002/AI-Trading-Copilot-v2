from services.certification.task8_live_candidate_adapter import (
    _policy_source,
)


def test_policy_source_preserves_explicit_certified_policy():
    value = _policy_source(
        {
            "policy_direction": "BEARISH",
            "policy_eligibility": "ELIGIBLE",
            "policy_confidence": 82.0,
            "policy_score": 77.0,
            "policy_reasons": ("explicit-policy",),
            "strategy": {
                "direction": "BULLISH",
                "decision": "NO_TRADE",
                "direction_confidence": 10.0,
                "evidence_strength_score": 10.0,
            },
        }
    )

    assert value.direction == "BEARISH"
    assert value.eligibility == "ELIGIBLE"
    assert value.confidence == 82.0
    assert value.score == 77.0
    assert value.reasons == ("explicit-policy",)
    assert "CERTIFIED_POLICY_EVIDENCE_UNAVAILABLE" not in value.blockers


def test_policy_source_maps_live_strategy_trade():
    value = _policy_source(
        {
            "strategy": {
                "direction": "BULLISH",
                "decision": "TRADE",
                "confidence": 76.0,
                "direction_confidence": 76.0,
                "evidence_strength_score": 73.0,
                "confirmations": (
                    "Bullish market regime",
                    "Technical analysis bullish",
                ),
                "risk_flags": (),
            }
        }
    )

    assert value.direction == "BULLISH"
    assert value.eligibility == "ELIGIBLE"
    assert value.confidence == 76.0
    assert value.score == 73.0
    assert value.reasons == (
        "Bullish market regime",
        "Technical analysis bullish",
    )
    assert value.warnings == ()
    assert "CERTIFIED_POLICY_EVIDENCE_UNAVAILABLE" not in value.blockers


def test_policy_source_maps_live_strategy_no_trade():
    value = _policy_source(
        {
            "strategy": {
                "direction": "BEARISH",
                "decision": "NO_TRADE",
                "direction_confidence": 58.0,
                "evidence_strength_score": 47.0,
                "confirmations": (),
                "risk_flags": (
                    "Conflicting timeframe signals",
                ),
            }
        }
    )

    assert value.direction == "BEARISH"
    assert value.eligibility == "INELIGIBLE"
    assert value.confidence == 58.0
    assert value.score == 47.0
    assert value.warnings == (
        "Conflicting timeframe signals",
    )
    assert "CERTIFIED_POLICY_EVIDENCE_UNAVAILABLE" not in value.blockers


def test_policy_source_keeps_legacy_analysis_fail_closed():
    value = _policy_source(
        {
            "legacy_decision": "BUY",
            "legacy_confidence": 99.0,
        }
    )

    assert value.direction == "UNAVAILABLE"
    assert value.eligibility == "UNAVAILABLE"
    assert value.confidence == 0.0
    assert value.score == 0.0
    assert "CERTIFIED_POLICY_EVIDENCE_UNAVAILABLE" in value.blockers


def test_policy_source_rejects_incomplete_strategy():
    value = _policy_source(
        {
            "strategy": {
                "direction": "BULLISH",
                "decision": "TRADE",
                "direction_confidence": 80.0,
            }
        }
    )

    assert value.direction == "UNAVAILABLE"
    assert value.eligibility == "UNAVAILABLE"
    assert "CERTIFIED_POLICY_EVIDENCE_UNAVAILABLE" in value.blockers


def test_policy_source_rejects_unknown_strategy_decision():
    value = _policy_source(
        {
            "strategy": {
                "direction": "BULLISH",
                "decision": "UNKNOWN",
                "direction_confidence": 80.0,
                "evidence_strength_score": 75.0,
            }
        }
    )

    assert value.direction == "UNAVAILABLE"
    assert value.eligibility == "UNAVAILABLE"
    assert "CERTIFIED_POLICY_EVIDENCE_UNAVAILABLE" in value.blockers
    assert "UNSUPPORTED_STRATEGY_DECISION" in value.blockers

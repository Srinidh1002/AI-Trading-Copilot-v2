from datetime import datetime, timezone

import pytest

from services.contracts.canonical_directional_policy_v1 import CanonicalDirectionalPolicyV1


def _policy(**changes):
    values = dict(policy_id="policy-1", symbol="NIFTY", exchange="NSE", evaluated_at=datetime.now(timezone.utc), direction="BULLISH", decision="TRADE", agreement_strength=80, evidence_strength=70, confidence=75, score=68, supporting_families=("TECHNICAL",), source_ids=("capture-1",))
    values.update(changes)
    return CanonicalDirectionalPolicyV1(**values)


@pytest.mark.parametrize("direction,decision", [("BULLISH", "TRADE"), ("BEARISH", "TRADE"), ("NEUTRAL", "NO_TRADE"), ("UNAVAILABLE", "UNAVAILABLE")])
def test_policy_accepts_valid_fail_closed_states(direction, decision):
    assert _policy(direction=direction, decision=decision).direction == direction


@pytest.mark.parametrize("changes", [{"confidence": 101}, {"evaluated_at": datetime.now()}, {"symbol": "BANKNIFTY"}, {"supporting_families": ("TECHNICAL", "TECHNICAL")}, {"supporting_families": ["TECHNICAL"]}])
def test_policy_rejects_invalid_values(changes):
    with pytest.raises((TypeError, ValueError)):
        _policy(**changes)


def test_unavailable_cannot_trade_and_metadata_is_immutable():
    with pytest.raises(ValueError, match="unavailable"):
        _policy(direction="UNAVAILABLE", decision="TRADE")
    policy = _policy(metadata={"source": ["a"]})
    assert policy.metadata["source"] == ("a",)
    with pytest.raises(TypeError):
        policy.metadata["source"] = "b"

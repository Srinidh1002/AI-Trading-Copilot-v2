"""Deterministic four-market replay of the isolated public regime API."""
import json
from datetime import timedelta

import pytest

from services.contracts.market_regime_policy_v1 import DEFAULT_MARKET_REGIME_POLICY, MarketRegimePolicyV1
from services.market_regime import evaluate_market_regime
from tests.fixtures.p5_10j_market_regime_replay import IDENTITIES, TS, input_for, replay_cases, session, technical


EXPECTED_PRIMARY = {
    "nifty_strong_bullish": "STRONG_BULLISH", "banknifty_event_risk": "EVENT_RISK",
    "finnifty_high_volatility": "HIGH_VOLATILITY", "sensex_blocked_session": "BLOCKED",
    "nifty_conflicting": "CONFLICTING", "banknifty_optional_missing": "STRONG_BULLISH",
    "finnifty_timestamp_skew": "STRONG_BULLISH", "sensex_unavailable": "BLOCKED",
}


@pytest.mark.parametrize("name,market_input", replay_cases().items())
def test_named_replays_have_stable_golden_identity_status_and_provenance(name, market_input):
    result = evaluate_market_regime(market_input)
    assert (result.underlying_symbol, result.exchange) == (market_input.underlying_symbol, market_input.exchange)
    assert result.primary_regime == EXPECTED_PRIMARY[name]
    assert result.market_regime_result_id == f"market-regime:{market_input.market_regime_input_id}"
    assert result.created_at == TS
    assert result.execution_mode == "PAPER" and result.live_execution_eligible is False
    assert result.to_dict() == evaluate_market_regime(market_input).to_dict()
    assert result.to_json() == evaluate_market_regime(market_input).to_json()
    assert result.semantic_dict() == evaluate_market_regime(market_input).semantic_dict()


@pytest.mark.parametrize("identity", IDENTITIES)
def test_equivalent_directional_evidence_is_market_neutral(identity):
    result = evaluate_market_regime(input_for(identity, identifier=f"neutral-{identity[0]}"))
    assert result.primary_regime == "STRONG_BULLISH"
    assert result.trend_state == "UPTREND"
    assert result.regime_strength == pytest.approx(0.9, abs=1e-12)
    assert result.confidence == 0.8


def test_boundary_and_policy_variants_remain_deterministic():
    exact_age = input_for(IDENTITIES[0], identifier="age-boundary", technical_component=technical(IDENTITIES[0], timestamp=TS - timedelta(seconds=300)))
    assert evaluate_market_regime(exact_age).primary_regime == "STRONG_BULLISH"
    policy = MarketRegimePolicyV1(technical_weight=2, broader_market_weight=1, external_context_weight=1, minimum_confirmation_count=0)
    result = evaluate_market_regime(input_for(IDENTITIES[0], identifier="weight-variant"), policy)
    assert result.primary_regime == "STRONG_BULLISH"
    assert json.loads(result.to_json())["source_timestamps"]["TECHNICAL"] == TS.isoformat()


def test_failure_replay_preserves_contract_exceptions():
    with pytest.raises(TypeError):
        evaluate_market_regime({})
    with pytest.raises(TypeError):
        evaluate_market_regime(input_for(IDENTITIES[0], identifier="bad-policy"), {})

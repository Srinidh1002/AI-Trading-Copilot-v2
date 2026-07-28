"""P5-10K1 package-surface and architecture certification preparation."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from services.contracts import (
    CanonicalMarketRegimeResultV1,
    DEFAULT_MARKET_REGIME_POLICY,
    MarketRegimeInputV1,
    MarketRegimePolicyV1,
)
from services.contracts.broader_market_regime_component_result_v1 import BroaderMarketRegimeComponentResultV1
from services.contracts.external_context_regime_component_result_v1 import ExternalContextRegimeComponentResultV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.technical_regime_component_result_v1 import TechnicalRegimeComponentResultV1
from services.market_regime import aggregate_market_regime, evaluate_market_regime
from services.market_regime import service
from services.market_regime.broader import evaluate_broader_market_regime_component
from services.market_regime.external import evaluate_external_context_regime_component
from services.market_regime.technical import evaluate_technical_regime_component
from tests.fixtures.p5_10j_market_regime_replay import IDENTITIES, input_for, replay_cases


ROOT = Path(__file__).resolve().parents[1]
P5_10_MODULES = (
    "services/contracts/market_regime_input_v1.py",
    "services/contracts/market_regime_policy_v1.py",
    "services/contracts/canonical_market_regime_result_v1.py",
    "services/contracts/technical_regime_component_result_v1.py",
    "services/contracts/broader_market_regime_component_result_v1.py",
    "services/contracts/external_context_regime_component_result_v1.py",
    "services/market_regime/technical.py",
    "services/market_regime/broader.py",
    "services/market_regime/external.py",
    "services/market_regime/aggregate.py",
    "services/market_regime/service.py",
)


def test_public_surface_and_expected_manifest_are_available():
    assert all((ROOT / path).is_file() for path in P5_10_MODULES)
    assert all((
        MarketRegimeInputV1, MarketRegimePolicyV1, DEFAULT_MARKET_REGIME_POLICY,
        CanonicalMarketRegimeResultV1, TechnicalRegimeComponentResultV1,
        BroaderMarketRegimeComponentResultV1, ExternalContextRegimeComponentResultV1,
        MarketSessionValidationV1, evaluate_technical_regime_component,
        evaluate_broader_market_regime_component, evaluate_external_context_regime_component,
        aggregate_market_regime, evaluate_market_regime,
    ))


def test_default_policy_certifies_ownership_freshness_thresholds_and_precedence():
    policy = DEFAULT_MARKET_REGIME_POLICY
    assert policy.required_components == ("TECHNICAL", "MARKET_SESSION")
    assert policy.optional_components == ("BROADER_MARKET", "EXTERNAL_CONTEXT")
    assert (policy.technical_weight, policy.broader_market_weight, policy.external_context_weight) == (0.60, 0.25, 0.15)
    assert dict(policy.maximum_component_age_seconds) == {"TECHNICAL": 300.0, "BROADER_MARKET": 600.0, "EXTERNAL_CONTEXT": 900.0, "MARKET_SESSION": 300.0}
    assert (policy.future_timestamp_tolerance_seconds, policy.maximum_component_timestamp_skew_seconds) == (5.0, 900.0)
    assert policy.high_volatility_override_states == ("HIGH", "EXTREME")
    assert policy.event_risk_override_states == ("HIGH", "EXTREME")
    assert policy.blocking_event_risk_states == ("EXTREME",)
    assert all(getattr(policy, name) is True for name in ("block_when_analysis_disallowed", "preserve_session_owned_restriction", "use_most_restrictive_entry_policy", "block_on_required_component_failure", "warn_on_optional_component_failure"))
    assert policy.aggregate_status_precedence == ("BLOCKED", "EVENT_RISK", "CONFLICTING", "HIGH_VOLATILITY", "UNAVAILABLE", "DIRECTIONAL")
    assert (policy.bullish_strength_threshold, policy.strong_bullish_strength_threshold, policy.bearish_strength_threshold, policy.strong_bearish_strength_threshold) == (0.55, 0.75, 0.55, 0.75)
    assert (policy.minimum_regime_confidence, policy.strong_regime_confidence_threshold, policy.caution_confidence_threshold, policy.suitable_confidence_threshold, policy.minimum_confirmation_count) == (0.50, 0.75, 0.50, 0.70, 1)
    assert (policy.conflict_penalty, policy.missing_optional_component_penalty, policy.warning_penalty, policy.partial_confirmation_penalty) == (0.20, 0.05, 0.05, 0.10)
    assert "MARKET_SESSION" not in policy.component_weights
    with pytest.raises(FrozenInstanceError):
        policy.technical_weight = 0.1


@pytest.mark.parametrize("identity", IDENTITIES)
def test_four_market_public_path_is_deterministic_paper_only(identity):
    market_input = input_for(identity, identifier=f"cert-{identity[0]}")
    result = evaluate_market_regime(market_input)
    assert type(result) is CanonicalMarketRegimeResultV1
    assert (result.underlying_symbol, result.exchange) == identity
    assert result.market_regime_result_id == f"market-regime:cert-{identity[0]}"
    assert result.created_at == market_input.created_at
    assert result.execution_mode == "PAPER" and result.live_execution_eligible is False
    assert result.to_dict() == evaluate_market_regime(market_input).to_dict()
    assert result.to_json() == evaluate_market_regime(market_input).to_json()
    assert result.semantic_dict() == evaluate_market_regime(market_input).semantic_dict()


def test_representative_outcomes_satisfy_canonical_coherence():
    results = {name: evaluate_market_regime(value) for name, value in replay_cases().items()}
    assert results["nifty_strong_bullish"].primary_regime in {"STRONG_BULLISH", "BULLISH", "RANGE_BOUND", "BEARISH", "STRONG_BEARISH"}
    assert results["banknifty_event_risk"].event_risk_state in {"HIGH", "EXTREME"}
    assert results["banknifty_event_risk"].entry_suitability != "SUITABLE"
    assert results["nifty_conflicting"].context_status == "CONFLICTING" and results["nifty_conflicting"].contradictions
    assert results["finnifty_high_volatility"].volatility_state in {"HIGH", "EXTREME"}
    required_failure = results["sensex_unavailable"]
    assert required_failure.context_status == "BLOCKED"
    assert required_failure.primary_regime == "BLOCKED"
    assert required_failure.blockers
    assert required_failure.entry_suitability == "BLOCKED"
    assert required_failure.new_entries_allowed is False
    blocked = results["sensex_blocked_session"]
    assert blocked.context_status == "BLOCKED" and blocked.blockers and blocked.entry_suitability == "BLOCKED" and blocked.new_entries_allowed is False


def test_service_delegates_once_and_propagates_aggregate_errors(monkeypatch):
    market_input = input_for(IDENTITIES[0], identifier="cert-delegation")
    sentinel = object()
    calls = []
    def aggregate_once(received_input, received_policy):
        calls.append((received_input, received_policy))
        return sentinel
    monkeypatch.setattr(service, "aggregate_market_regime", aggregate_once)
    assert service.evaluate_market_regime(market_input, DEFAULT_MARKET_REGIME_POLICY) is sentinel
    assert calls == [(market_input, DEFAULT_MARKET_REGIME_POLICY)]
    monkeypatch.setattr(service, "aggregate_market_regime", lambda *_: (_ for _ in ()).throw(ValueError("certified")))
    with pytest.raises(ValueError, match="certified"):
        service.evaluate_market_regime(market_input)


def test_ast_boundaries_exclude_runtime_and_unsafe_calls():
    forbidden_imports = {"dashboard", "broker", "execution", "decision", "ranking", "strategy", "portfolio", "streamlit", "yfinance", "openai", "requests"}
    forbidden_calls = {"now", "utcnow", "today", "uuid4", "time", "open", "write_text", "write_bytes"}
    for relative_path in P5_10_MODULES:
        tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
        imports = {alias.name.split(".")[0].lower() for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
        calls = {node.func.attr.lower() for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        assert not imports & forbidden_imports
        assert not calls & forbidden_calls

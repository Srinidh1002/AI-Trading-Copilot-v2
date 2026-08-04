"""Focused package-isolated P5-10I integration coverage."""
from inspect import signature

import pytest

from services.contracts.market_regime_input_v1 import MarketRegimeInputV1
from services.contracts.market_regime_policy_v1 import DEFAULT_MARKET_REGIME_POLICY, MarketRegimePolicyV1
from services.market_regime import evaluate_market_regime
from services.market_regime import service


def test_public_api_has_the_certified_default_policy():
    assert evaluate_market_regime is service.evaluate_market_regime
    assert signature(evaluate_market_regime).parameters["policy"].default is DEFAULT_MARKET_REGIME_POLICY


@pytest.mark.parametrize("value", (object(), {}, None))
def test_input_requires_exact_contract(value):
    with pytest.raises(TypeError):
        evaluate_market_regime(value)


@pytest.mark.parametrize("value", (object(), {}, None))
def test_policy_requires_exact_contract(value):
    with pytest.raises(TypeError):
        evaluate_market_regime(object(), value)


def test_service_delegates_once_with_the_original_objects(monkeypatch):
    input_value = object.__new__(MarketRegimeInputV1)
    policy_value = object.__new__(MarketRegimePolicyV1)
    expected = object()
    calls = []

    def aggregate_once(received_input, received_policy):
        calls.append((received_input, received_policy))
        return expected

    monkeypatch.setattr(service, "aggregate_market_regime", aggregate_once)
    assert service.evaluate_market_regime(input_value, policy_value) is expected
    assert calls == [(input_value, policy_value)]

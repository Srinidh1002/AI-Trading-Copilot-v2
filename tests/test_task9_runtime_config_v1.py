from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from services.contracts.task9_runtime_config_v1 import (
    ProviderFeatureStateV1,
    Task9MarketRuntimeIdentityV1,
    Task9RuntimeConfigV1,
)


def _config(**overrides):
    values = {
        "runtime_config_id": "task9-runtime-20260815",
        "runtime_config_version": "1",
        "market_date": date(2026, 8, 15),
        "campaign_registry_location": "artifacts/task9/campaign-registry",
        "campaign_id": "campaign-20260815",
        "official_run_id": "run-20260815",
        "official_root": "artifacts/task9/official",
        "certification_registry_root": "artifacts/task9/certification-registry",
        "authoritative_persistence_root": "artifacts/task9/runtime",
        "dashboard_publication_location": "artifacts/task9/dashboard",
        "available_capital": 10000.0,
        "trade_risk_fraction": 0.02,
        "maximum_daily_loss_fraction": 0.05,
        "maximum_lots": 1,
        "maximum_quantity": 50,
        "maximum_spread_fraction": 0.10,
        "parent_cycle_cadence_seconds": 60.0,
        "collector_heartbeat_seconds": 5.0,
        "market_quote_max_age_seconds": 300.0,
        "option_quote_max_age_seconds": 1.0,
        "instrument_master_max_age_seconds": 86400.0,
        "policy_references": {
            "canonical_directional": "directional.v1", "session": "session.v1",
            "risk": "risk.v1", "contract_selection": "selection.v1",
            "lifecycle": "lifecycle.v1", "counting": "counting.v1",
            "failure_disposition": "future", "contract_spread": "spread.v1",
            "liquidity": "liquidity.v1", "minimum_risk_reward": "rr.v1",
            "stop_target": "stop-target.v1", "portfolio_concurrency": "portfolio.v1",
        },
        "angel_api_key_env_name": "ANGEL_API_KEY",
        "angel_client_id_env_name": "ANGEL_CLIENT_ID",
        "angel_pin_env_name": "ANGEL_PIN",
        "angel_totp_secret_env_name": "ANGEL_TOTP_SECRET",
    }
    values.update(overrides)
    return Task9RuntimeConfigV1(**values)


def test_valid_paper_config_is_immutable_and_round_trips():
    config = _config()
    with pytest.raises(FrozenInstanceError):
        config.runtime_config_id = "other"
    assert config.to_json() == config.to_json()
    assert Task9RuntimeConfigV1.from_dict(config.to_dict()) == config


@pytest.mark.parametrize("name, value", [
    ("execution_mode", "LIVE"), ("broker_order_submission", True),
    ("live_execution_eligible", True), ("timezone", ""),
    ("market_date", "2026-08-15"), ("available_capital", 0),
    ("trade_risk_fraction", 1.1), ("maximum_spread_fraction", 1.1),
    ("maximum_lots", -1), ("maximum_quantity", -1),
    ("official_root", ""),
])
def test_invalid_runtime_values_are_rejected(name, value):
    with pytest.raises((TypeError, ValueError)):
        _config(**{name: value})


@pytest.mark.parametrize("markets", [
    (Task9MarketRuntimeIdentityV1("NIFTY", "NSE", "99926000", "NFO"), Task9MarketRuntimeIdentityV1("SENSEX", "BSE", "99919000", "BFO")),
])
def test_market_identities_are_canonical(markets):
    assert _config(markets=markets).markets == markets
    with pytest.raises(ValueError):
        Task9MarketRuntimeIdentityV1("NIFTY", "BSE", "99926000", "NFO")
    with pytest.raises(ValueError):
        Task9MarketRuntimeIdentityV1("SENSEX", "BSE", "99919000", "NFO")
    with pytest.raises(ValueError):
        Task9MarketRuntimeIdentityV1("NIFTY", "NSE", "99926000", "BFO")
    with pytest.raises(ValueError):
        Task9MarketRuntimeIdentityV1("SENSEX", "BSE", "wrong", "BFO")


def test_provider_intent_and_reference_only_secrets():
    config = _config()
    assert config.provider_features["market_breadth"] is ProviderFeatureStateV1.PROVIDER_NOT_SELECTED
    assert config.provider_features["llm"] is ProviderFeatureStateV1.OPTIONAL_FUTURE
    assert config.provider_features["angel_greeks"] is ProviderFeatureStateV1.CAPABILITY_AWARE
    assert "ANGEL_API_KEY" in config.to_json()
    with pytest.raises(ValueError):
        _config(angel_api_key_env_name="secret-value")
    features = dict(config.provider_features)
    features["llm"] = ProviderFeatureStateV1.DISABLED
    disabled = _config(provider_features=features)
    assert disabled.provider_features["llm"] is ProviderFeatureStateV1.DISABLED
    assert disabled.provider_features["market_breadth"] is not disabled.provider_features["llm"]


def test_run_classification_is_reused():
    assert _config(run_classification="diagnostic_non_counting").run_classification == "DIAGNOSTIC_NON_COUNTING"
    with pytest.raises(ValueError):
        _config(run_classification="unsupported")

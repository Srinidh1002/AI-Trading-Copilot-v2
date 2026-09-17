from datetime import date

import pytest

from services.certification.task9_runtime_config_builder import (
    build_task9_runtime_config,
    detect_task9_legacy_conflicts,
)
from services.contracts.task9_runtime_config_v1 import (
    ProviderFeatureStateV1,
    Task9RuntimeConfigV1,
)


_POLICIES = {
    "canonical_directional": "directional.v1", "session": "session.v1",
    "risk": "risk.v1", "contract_selection": "selection.v1",
    "lifecycle": "lifecycle.v1", "counting": "counting.v1",
    "failure_disposition": "future", "contract_spread": "spread.v1",
    "liquidity": "liquidity.v1", "minimum_risk_reward": "rr.v1",
    "stop_target": "stop-target.v1", "portfolio_concurrency": "portfolio.v1",
}
_LEGACY_CONFLICT = {
    "config_capital": 100000, "trading_runtime_capital": 10000,
    "config_risk_fraction": 0.02, "trading_runtime_risk_percent": 1.0,
    "legacy_broker": "LIVE", "legacy_enable_live_trading": True,
    "legacy_nifty_token": "not-a-canonical-token",
}


def _build(**overrides):
    values = {
        "runtime_config_id": "runtime-1", "runtime_config_version": "1",
        "campaign_registry_location": "task9/campaigns", "campaign_id": "campaign-1",
        "market_date": date(2026, 8, 15), "official_run_id": "run-1",
        "official_root": "task9/official", "certification_registry_root": "task9/registry",
        "authoritative_persistence_root": "task9/runtime", "dashboard_publication_location": "task9/dashboard",
        "available_capital": 25000.0, "risk_fraction": 0.02,
        "maximum_quantity": 50, "policy_references": _POLICIES,
        "legacy_values": _LEGACY_CONFLICT,
    }
    values.update(overrides)
    return build_task9_runtime_config(**values)


def test_explicit_operational_inputs_build_canonical_paper_config():
    config = _build()
    assert type(config) is Task9RuntimeConfigV1
    assert (config.execution_mode, config.broker_order_submission, config.live_execution_eligible) == ("PAPER", False, False)
    assert [(item.market, item.exchange, item.spot_token, item.option_exchange) for item in config.markets] == [
        ("NIFTY", "NSE", "99926000", "NFO"), ("SENSEX", "BSE", "99919000", "BFO"),
    ]


@pytest.mark.parametrize("name, value", [
    ("execution_mode", "LIVE"), ("broker_order_submission", True),
    ("live_execution_eligible", True), ("risk_fraction", 1.1),
])
def test_unsafe_or_invalid_explicit_values_are_rejected(name, value):
    with pytest.raises(ValueError):
        _build(**{name: value})


def test_ambiguous_legacy_values_never_supply_capital_or_risk():
    assert detect_task9_legacy_conflicts(_LEGACY_CONFLICT) == frozenset({"capital", "risk_fraction"})
    with pytest.raises(ValueError, match="available_capital"):
        _build(available_capital=None)
    with pytest.raises(ValueError, match="risk_fraction"):
        _build(risk_fraction=None)
    config = _build(available_capital=25000.0, risk_fraction=0.02)
    assert (config.available_capital, config.trade_risk_fraction) == (25000.0, 0.02)
    assert "risk_fraction" in detect_task9_legacy_conflicts({
        "config_risk_fraction": 0.02, "settings_risk_fraction": 0.01,
    })


def test_secrets_are_references_only_and_legacy_market_data_is_ignored():
    config = _build()
    document = config.to_dict()
    assert config.angel_api_key_env_name == "ANGEL_API_KEY"
    assert config.angel_client_id_env_name == "ANGEL_CLIENT_ID"
    assert "ANGEL_TOTP_SECRET" in config.to_json()
    assert "super-secret" not in config.to_json()
    assert all(item.market in {"NIFTY", "SENSEX"} for item in config.markets)
    assert document["markets"][0]["spot_token"] == "99926000"


def test_output_is_deterministic_and_round_trips():
    first = _build()
    second = _build()
    assert first.to_json() == second.to_json()
    assert Task9RuntimeConfigV1.from_dict(first.to_dict()) == first


def test_provider_intent_is_frozen_and_legacy_live_flags_do_not_override_it():
    config = _build()
    assert config.provider_features["angel_spot"] is ProviderFeatureStateV1.ENABLED_REQUIRED
    assert config.provider_features["india_vix"] is ProviderFeatureStateV1.ENABLED_OPTIONAL
    for name in ("market_breadth", "fii_dii", "events", "global", "news"):
        assert config.provider_features[name] is ProviderFeatureStateV1.PROVIDER_NOT_SELECTED
    assert config.provider_features["llm"] in {ProviderFeatureStateV1.OPTIONAL_FUTURE, ProviderFeatureStateV1.DISABLED}

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.broker.fyers_data_compatibility_v2 import (
    FyersDataOnlyCompatibilityV2,
)
from services.certification import fyers_task8_provider_composition_v2 as mod
from services.certification.fyers_task8_provider_composition_v2 import (
    FyersHistoricalProviderCooldownV2,
    FyersTask8CompositionError,
    build_fyers_parent_quote_reader_v2,
    build_fyers_task8_dependencies_v2,
    build_fyers_task8_provider_bundle_v2,
)
from services.paper_orchestration.certified_runtime_composition import (
    CertifiedRuntimeProviderBundleV1,
)


NOW = datetime(2026, 10, 5, 7, 30, tzinfo=timezone.utc)


class FakeFyersClient:
    def __init__(self, *, quote_timestamp=None):
        self.quote_timestamp = int(
            (quote_timestamp or NOW).timestamp()
        )
        self.quote_calls = []

    def quotes(self, data=None):
        self.quote_calls.append(data)
        symbol = data["symbols"]
        return {
            "s": "ok",
            "code": 200,
            "d": [
                {
                    "n": symbol,
                    "v": {
                        "symbol": symbol,
                        "lp": 22462.5,
                        "bid": 22462.0,
                        "ask": 22463.0,
                        "volume": 1000,
                        "tt": self.quote_timestamp,
                        "fyToken": "FY-SPOT",
                    },
                }
            ],
        }

    def history(self, data=None):
        return {
            "s": "ok",
            "candles": [
                [
                    int((NOW - timedelta(minutes=10)).timestamp()),
                    100.0,
                    101.0,
                    99.0,
                    100.5,
                    1000,
                ]
            ],
        }

    def depth(self, data=None):
        symbol = data["symbol"]
        return {
            "s": "ok",
            "d": {
                symbol: {
                    "ltp": 100.0,
                    "bids": [{"price": 99.5, "volume": 10}],
                    "ask": [{"price": 100.5, "volume": 10}],
                }
            },
        }

    def optionchain(self, data=None):
        return {
            "s": "ok",
            "data": {
                "expiryData": [],
                "optionsChain": [],
            },
        }

    def futures_chain(self, data=None):
        return {"s": "ok", "data": []}


class FakeMasterStore:
    def get_index(self, segment):
        raise AssertionError(
            f"master store should not be read during composition: {segment}"
        )


def legacy_api(client=None):
    client = client or FakeFyersClient()

    def resolver(exchange, tradingsymbol, symboltoken):
        if symboltoken == "99926000":
            assert exchange == "NSE"
            assert tradingsymbol in ("NIFTY", None)
            return "NSE:NIFTY50-INDEX"
        if symboltoken == "99919000":
            assert exchange == "BSE"
            assert tradingsymbol in ("SENSEX", None)
            return "BSE:SENSEX-INDEX"
        raise KeyError(symboltoken)

    return FyersDataOnlyCompatibilityV2(
        client=client,
        symbol_resolver=resolver,
    )


def test_parent_quote_reader_returns_fresh_fyers_provenance():
    client = FakeFyersClient()
    reader = build_fyers_parent_quote_reader_v2(
        legacy_data_api=legacy_api(client),
        clock=lambda: NOW,
    )

    result = reader(
        "NSE",
        "99926000",
        "NIFTY",
    )

    assert result["provider"] == "FYERS"
    assert result["spot_price"] == 22462.5
    assert result["market_timestamp"] == NOW
    assert result["received_at"] == NOW
    assert result["timestamp_source"] == "FYERS_PROVIDER_TT"
    assert result["provider_timestamp_field"] == "tt"
    assert result["quote_age_seconds"] == 0.0
    assert client.quote_calls == [
        {"symbols": "NSE:NIFTY50-INDEX"}
    ]


def test_parent_quote_reader_fails_closed_on_stale_quote():
    client = FakeFyersClient(
        quote_timestamp=NOW - timedelta(minutes=6)
    )
    reader = build_fyers_parent_quote_reader_v2(
        legacy_data_api=legacy_api(client),
        clock=lambda: NOW,
        maximum_quote_age_seconds=300.0,
    )

    with pytest.raises(
        FyersTask8CompositionError,
        match="FYERS_PARENT_QUOTE_STALE",
    ):
        reader("NSE", "99926000", "NIFTY")


def test_parent_quote_reader_rejects_identity_mismatch():
    api = legacy_api()

    def bad_ltp(exchange, tradingsymbol, symboltoken):
        return {
            "status": True,
            "data": {
                "exchange": "BSE",
                "tradingsymbol": "NIFTY",
                "symboltoken": symboltoken,
                "ltp": 22462.5,
                "exchange_timestamp": int(NOW.timestamp()),
            },
        }

    api.ltpData = bad_ltp
    reader = build_fyers_parent_quote_reader_v2(
        legacy_data_api=api,
        clock=lambda: NOW,
    )

    with pytest.raises(
        FyersTask8CompositionError,
        match="FYERS_PARENT_QUOTE_IDENTITY_MISMATCH",
    ):
        reader("NSE", "99926000", "NIFTY")


def test_provider_bundle_is_fyers_data_only_and_uses_isolated_history_state(
    tmp_path,
):
    bundle = build_fyers_task8_provider_bundle_v2(
        data_client=FakeFyersClient(),
        master_store=FakeMasterStore(),
        state_root=tmp_path / "fyers_task8",
        clock=lambda: NOW,
    )

    assert type(bundle) is CertifiedRuntimeProviderBundleV1

    data_service = bundle.analysis_pipeline.data_service
    assert data_service.provider_source == "FYERS_HISTORICAL"
    assert data_service.cache_enabled is False
    assert isinstance(
        data_service.provider_cooldown,
        FyersHistoricalProviderCooldownV2,
    )
    assert data_service.provider_cooldown.PROVIDER == "FYERS"
    assert (
        data_service.cache.file_path
        == tmp_path / "fyers_task8" / "historical_data_cache.json"
    )

    option_builder = (
        bundle.option_decision_pipeline.option_chain_builder
    )
    assert option_builder.data_only is True
    assert option_builder.order_capability_allowed is False
    assert option_builder.automatic_fallback_allowed is False


def test_dependency_wrapper_injects_fyers_parent_reader_and_explicit_preflight(
    tmp_path,
    monkeypatch,
):
    captured = {}

    def fake_build_task8_dependencies(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(marker="dependencies")

    monkeypatch.setattr(
        mod,
        "build_task8_dependencies",
        fake_build_task8_dependencies,
    )

    def preflight():
        return {
            "branch_worktree": True,
            "paper_mode": True,
            "live_execution_ineligible": True,
            "broker_submission_disabled": True,
            "nifty_provider": True,
            "sensex_provider": True,
            "routing": True,
            "persistence_writable": True,
            "journal_writable": True,
            "emergency_halt": True,
            "market_session_checked": True,
            "credentials_present": True,
            "journal_status": "NOT_WRITTEN",
        }

    result = build_fyers_task8_dependencies_v2(
        data_client=FakeFyersClient(),
        preflight_authority=preflight,
        master_store=FakeMasterStore(),
        state_root=tmp_path / "fyers_task8",
        clock=lambda: NOW,
    )

    assert result.marker == "dependencies"
    assert type(captured["providers"]) is CertifiedRuntimeProviderBundleV1
    assert captured["parent_quote_reader"] is captured["providers"].quote_reader
    assert captured["preflight_override"] is preflight


def test_dependency_wrapper_requires_explicit_preflight_authority():
    with pytest.raises(TypeError, match="preflight_authority"):
        build_fyers_task8_dependencies_v2(
            data_client=FakeFyersClient(),
            preflight_authority=None,
            master_store=FakeMasterStore(),
            clock=lambda: NOW,
        )



def test_fyers_task8_composition_has_no_order_or_live_execution_surface():
    source = Path(
        "services/certification/fyers_task8_provider_composition_v2.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "placeOrder(",
        "place_order(",
        "submit_order(",
        "modifyOrder(",
        "cancelOrder(",
        "FyersOrderSocket",
        "live_execution_eligible=True",
        "broker_order_submission=True",
    )
    assert not [marker for marker in forbidden if marker in source]

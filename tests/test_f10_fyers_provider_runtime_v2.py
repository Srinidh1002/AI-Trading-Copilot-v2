from __future__ import annotations

from pathlib import Path

import pytest

from services.broker.fyers_provider_adapters_v2 import (
    FyersHistoricalDataProviderV2,
    FyersQuoteDepthProviderV2,
)
from services.broker.fyers_provider_runtime_v2 import (
    FyersRuntimeCompositionError,
    build_fyers_provider_runtime_v2,
)
from services.broker.provider_data_interfaces_v2 import (
    HistoricalDataProviderV2,
    InstrumentResolverV2,
    QuoteDepthProviderV2,
    StreamingMarketDataProviderV2,
)
from services.broker.provider_registry_v2 import (
    get_provider_registration,
    provider_adapter_ready,
)
from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.broker.shared_provider_orchestrator_v2 import (
    SharedProviderOrchestratorV2,
)
from services.contracts.provider_runtime_bundle_v2 import (
    ProviderRequestControllerV2,
    ProviderRuntimeBundleV2,
)
from services.core.provider_routing_policy_v2 import (
    automatic_fallback_provider,
    resolve_operational_primary,
    resolve_shadow_providers,
)


class FakeDataClient:
    pass


class FakeStreaming:
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(self):
        self.subscribe_calls = []
        self.unsubscribe_calls = []
        self.close_calls = 0

    def subscribe(self, instruments, callback):
        sid = f"f10-sub-{len(self.subscribe_calls) + 1}"
        self.subscribe_calls.append((tuple(instruments), callback, sid))
        return sid

    def unsubscribe(self, subscription_id):
        self.unsubscribe_calls.append(subscription_id)

    def close(self):
        self.close_calls += 1


class UnsafeStreaming(FakeStreaming):
    order_capability_allowed = True


class FakeController:
    def wait_for_slot(self, request_type, attempt):
        return 0.0

    def record_rate_limit(self, request_type, retry_number, backoff_multiplier):
        return 0.0

    def record_success(self, request_type):
        return None


def build_runtime():
    return build_fyers_provider_runtime_v2(
        data_client=FakeDataClient(),
        streaming=FakeStreaming(),
        request_controller=FakeController(),
    )


def test_runtime_composes_all_v2_capabilities():
    runtime = build_runtime()

    assert isinstance(runtime, ProviderRuntimeBundleV2)
    assert runtime.provider == "FYERS"
    assert isinstance(runtime.resolver, InstrumentResolverV2)
    assert isinstance(runtime.historical, HistoricalDataProviderV2)
    assert isinstance(runtime.quote_depth, QuoteDepthProviderV2)
    assert isinstance(runtime.streaming, StreamingMarketDataProviderV2)
    assert isinstance(runtime.request_controller, ProviderRequestControllerV2)

    assert isinstance(runtime.historical, FyersHistoricalDataProviderV2)
    assert isinstance(runtime.quote_depth, FyersQuoteDepthProviderV2)


def test_runtime_safety_contract_is_locked():
    runtime = build_runtime()
    assert runtime.data_only is True
    assert runtime.order_capability_allowed is False
    assert runtime.automatic_fallback_allowed is False


def test_runtime_rejects_order_capable_streaming():
    with pytest.raises(
        FyersRuntimeCompositionError,
        match="order capability",
    ):
        build_fyers_provider_runtime_v2(
            data_client=FakeDataClient(),
            streaming=UnsafeStreaming(),
        )


def test_runtime_requires_explicit_data_client():
    with pytest.raises(ValueError, match="data_client"):
        build_fyers_provider_runtime_v2(
            data_client=None,
            streaming=FakeStreaming(),
        )


def test_fyers_ready_but_angel_shadow_remains_pending():
    fyers = get_provider_registration("FYERS")
    angel = get_provider_registration("ANGEL_SMARTAPI")

    assert fyers.adapter_status == "READY"
    assert provider_adapter_ready("FYERS") is True

    assert angel.adapter_status == "PENDING_V2_ADAPTER"
    assert provider_adapter_ready("ANGEL_SMARTAPI") is False


def test_all_25_operational_primary_routes_resolve_only_fyers():
    markets = (
        "NIFTY",
        "SENSEX",
        "CRUDEOILM",
        "GOLDM",
        "SILVERM",
    )
    kinds = (
        "INSTRUMENT",
        "QUOTE",
        "DEPTH",
        "HISTORICAL",
        "STREAMING",
    )

    for market in markets:
        for kind in kinds:
            assert resolve_operational_primary(market, kind) == "FYERS"
            assert automatic_fallback_provider(market, kind) is None


def test_shadow_route_is_visible_but_not_operationally_ready():
    shadows = resolve_shadow_providers(
        "NIFTY",
        "QUOTE",
        require_ready=False,
    )
    assert shadows == ("ANGEL_SMARTAPI",)

    with pytest.raises(
        RuntimeError,
        match="PROVIDER_V2_ADAPTER_NOT_READY",
    ):
        resolve_shadow_providers(
            "NIFTY",
            "QUOTE",
            require_ready=True,
        )


def test_orchestrator_returns_installed_fyers_as_operational_primary():
    hub = SharedMarketDataHubV2()
    orchestrator = SharedProviderOrchestratorV2(market_data_hub=hub)
    runtime = build_runtime()
    orchestrator.install_runtime(runtime)

    acquired = orchestrator.get_operational_primary_runtime(
        market_symbol="NIFTY",
        data_kind="STREAMING",
        consumer_id="F10_TEST",
    )

    assert acquired is runtime
    assert orchestrator.snapshot()["consumer_counts"]["FYERS"] == 1


def test_orchestrator_uses_same_shared_streaming_instance():
    hub = SharedMarketDataHubV2()
    orchestrator = SharedProviderOrchestratorV2(market_data_hub=hub)
    runtime = build_runtime()
    orchestrator.install_runtime(runtime)

    sid = orchestrator.subscribe(
        provider="FYERS",
        consumer_id="NIFTY_ENGINE",
        instruments=({"provider_symbol": "NSE:NIFTY50-INDEX"},),
        callback=lambda item: None,
    )

    assert sid == "f10-sub-1"
    assert len(runtime.streaming.subscribe_calls) == 1

    orchestrator.unsubscribe(
        provider="FYERS",
        consumer_id="NIFTY_ENGINE",
    )
    orchestrator.release_runtime(
        provider="FYERS",
        consumer_id="NIFTY_ENGINE",
    )
    orchestrator.close_provider("FYERS")
    assert runtime.streaming.close_calls == 1


def test_f10_runtime_module_has_no_auth_env_sdk_or_order_authority():
    text = Path(
        "services/broker/fyers_provider_runtime_v2.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "load_dotenv",
        "os.getenv",
        "fyers_apiv3",
        "SmartConnect",
        "place_order",
        "placeOrder",
        "modify_order",
        "cancel_order",
        "FyersOrderSocket",
        "automatic_fallback_provider(",
    )

    assert not [marker for marker in forbidden if marker in text]

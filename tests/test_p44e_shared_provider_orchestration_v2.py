from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest

from services.broker.market_data_control import (
    MarketDataRequestController,
)
from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.broker.shared_provider_orchestrator_v2 import (
    ProviderRuntimeAlreadyInstalledError,
    ProviderRuntimeInUseError,
    SharedProviderOrchestratorV2,
)
from services.contracts.market_data_v2 import (
    ProviderHealthV2,
)
from services.contracts.provider_runtime_bundle_v2 import (
    ProviderRequestControllerV2,
    ProviderRuntimeBundleV2,
)


NOW = datetime(
    2026,
    9,
    16,
    10,
    0,
    tzinfo=timezone.utc,
)


class FakeResolver:
    def resolve(
        self,
        **kwargs,
    ):
        return {
            "provider_symbol": "TEST",
        }


class FakeHistorical:
    def get_candles(
        self,
        instrument,
        *,
        interval,
        start,
        end,
    ):
        return []


class FakeQuoteDepth:
    def get_quote(
        self,
        instrument,
    ):
        return {}

    def get_depth(
        self,
        instrument,
    ):
        return {}


class FakeStreaming:
    def __init__(self):
        self.subscribe_calls = []
        self.unsubscribe_calls = []
        self.close_calls = 0

    def subscribe(
        self,
        instruments,
        callback,
    ):
        subscription_id = (
            f"sub-{len(self.subscribe_calls) + 1}"
        )

        self.subscribe_calls.append(
            (
                tuple(instruments),
                callback,
                subscription_id,
            )
        )

        return subscription_id

    def unsubscribe(
        self,
        subscription_id,
    ):
        self.unsubscribe_calls.append(
            subscription_id
        )

    def close(self):
        self.close_calls += 1


class FakeController:
    def wait_for_slot(
        self,
        request_type,
        attempt,
    ):
        return 0.0

    def record_rate_limit(
        self,
        request_type,
        retry_number,
        backoff_multiplier,
    ):
        return 0.0

    def record_success(
        self,
        request_type,
    ):
        return None


def runtime(
    provider,
):
    return ProviderRuntimeBundleV2(
        provider=provider,
        resolver=FakeResolver(),
        historical=FakeHistorical(),
        quote_depth=FakeQuoteDepth(),
        streaming=FakeStreaming(),
        request_controller=FakeController(),
    )


def test_existing_angel_request_controller_satisfies_v2_control_protocol():
    controller = MarketDataRequestController(
        min_request_interval_seconds=0,
        historical_request_interval_seconds=0,
        market_quote_request_interval_seconds=0,
        historical_requests_per_second=1,
        historical_requests_per_minute=1,
        historical_requests_per_hour=1,
        cache_ttl_seconds=0,
        rate_limit_cooldown_seconds=0,
    )

    assert isinstance(
        controller,
        ProviderRequestControllerV2,
    )


def test_one_runtime_bundle_is_shared_by_multiple_consumers():
    hub = SharedMarketDataHubV2()

    orchestrator = (
        SharedProviderOrchestratorV2(
            market_data_hub=hub,
        )
    )

    bundle = runtime(
        "FYERS"
    )

    orchestrator.install_runtime(
        bundle
    )

    nifty = orchestrator.acquire_runtime(
        provider="FYERS",
        consumer_id="NIFTY_ENGINE",
    )

    crude = orchestrator.acquire_runtime(
        provider="FYERS",
        consumer_id="CRUDE_ENGINE",
    )

    assert nifty is bundle
    assert crude is bundle

    assert (
        nifty.request_controller
        is crude.request_controller
    )

    assert (
        nifty.streaming
        is crude.streaming
    )

    snapshot = orchestrator.snapshot()

    assert (
        snapshot["consumer_counts"]["FYERS"]
        == 2
    )


def test_duplicate_runtime_for_same_provider_is_rejected():
    orchestrator = (
        SharedProviderOrchestratorV2(
            market_data_hub=(
                SharedMarketDataHubV2()
            ),
        )
    )

    orchestrator.install_runtime(
        runtime("FYERS")
    )

    with pytest.raises(
        ProviderRuntimeAlreadyInstalledError,
        match="PROVIDER_RUNTIME_ALREADY_INSTALLED",
    ):
        orchestrator.install_runtime(
            runtime("FYERS")
        )


def test_primary_and_shadow_own_separate_shared_runtime_bundles():
    orchestrator = (
        SharedProviderOrchestratorV2(
            market_data_hub=(
                SharedMarketDataHubV2()
            ),
        )
    )

    fyers = runtime(
        "FYERS"
    )

    angel = runtime(
        "ANGEL_SMARTAPI"
    )

    orchestrator.install_runtime(
        fyers
    )

    orchestrator.install_runtime(
        angel
    )

    assert (
        orchestrator.get_explicit_runtime(
            "FYERS"
        )
        is fyers
    )

    assert (
        orchestrator.get_explicit_runtime(
            "ANGEL_SMARTAPI"
        )
        is angel
    )

    assert (
        fyers.request_controller
        is not angel.request_controller
    )


def test_operational_primary_remains_blocked_while_registry_is_pending():
    orchestrator = (
        SharedProviderOrchestratorV2(
            market_data_hub=(
                SharedMarketDataHubV2()
            ),
        )
    )

    orchestrator.install_runtime(
        runtime("FYERS")
    )

    orchestrator.install_runtime(
        runtime("ANGEL_SMARTAPI")
    )

    with pytest.raises(
        RuntimeError,
        match="PROVIDER_V2_ADAPTER_NOT_READY",
    ):
        orchestrator.get_operational_primary_runtime(
            market_symbol="NIFTY",
            data_kind="QUOTE",
            consumer_id="TEST",
        )


def test_shared_streaming_adapter_is_not_duplicated_per_consumer():
    orchestrator = (
        SharedProviderOrchestratorV2(
            market_data_hub=(
                SharedMarketDataHubV2()
            ),
        )
    )

    bundle = runtime(
        "FYERS"
    )

    orchestrator.install_runtime(
        bundle
    )

    callback = lambda item: None

    first = orchestrator.subscribe(
        provider="FYERS",
        consumer_id="NIFTY_ENGINE",
        instruments=(
            {"provider_symbol": "NIFTY"},
        ),
        callback=callback,
    )

    second = orchestrator.subscribe(
        provider="FYERS",
        consumer_id="SENSEX_ENGINE",
        instruments=(
            {"provider_symbol": "SENSEX"},
        ),
        callback=callback,
    )

    assert first == "sub-1"
    assert second == "sub-2"

    assert (
        len(
            bundle.streaming.subscribe_calls
        )
        == 2
    )

    assert (
        orchestrator.acquire_runtime(
            provider="FYERS",
            consumer_id="MCX_ENGINE",
        ).streaming
        is bundle.streaming
    )


def test_consumer_cannot_be_released_with_active_stream_subscription():
    orchestrator = (
        SharedProviderOrchestratorV2(
            market_data_hub=(
                SharedMarketDataHubV2()
            ),
        )
    )

    orchestrator.install_runtime(
        runtime("FYERS")
    )

    orchestrator.subscribe(
        provider="FYERS",
        consumer_id="NIFTY_ENGINE",
        instruments=(
            {"provider_symbol": "NIFTY"},
        ),
        callback=lambda item: None,
    )

    with pytest.raises(
        ProviderRuntimeInUseError,
        match="CONSUMER_STREAM_SUBSCRIPTION_ACTIVE",
    ):
        orchestrator.release_runtime(
            provider="FYERS",
            consumer_id="NIFTY_ENGINE",
        )


def test_provider_health_is_published_into_shared_market_data_hub():
    hub = SharedMarketDataHubV2()

    orchestrator = (
        SharedProviderOrchestratorV2(
            market_data_hub=hub,
        )
    )

    health = ProviderHealthV2(
        provider="FYERS",
        status="HEALTHY",
        checked_at=NOW,
        last_success_at=NOW,
        consecutive_failures=0,
    )

    orchestrator.publish_provider_health(
        health
    )

    assert (
        hub.get_provider_health(
            "FYERS"
        )
        == health
    )


def test_runtime_cannot_close_while_consumers_exist():
    orchestrator = (
        SharedProviderOrchestratorV2(
            market_data_hub=(
                SharedMarketDataHubV2()
            ),
        )
    )

    bundle = runtime(
        "FYERS"
    )

    orchestrator.install_runtime(
        bundle
    )

    orchestrator.acquire_runtime(
        provider="FYERS",
        consumer_id="NIFTY_ENGINE",
    )

    with pytest.raises(
        ProviderRuntimeInUseError,
        match="PROVIDER_RUNTIME_IN_USE",
    ):
        orchestrator.close_provider(
            "FYERS"
        )

    assert (
        bundle.streaming.close_calls
        == 0
    )


def test_clean_release_allows_one_provider_stream_close():
    orchestrator = (
        SharedProviderOrchestratorV2(
            market_data_hub=(
                SharedMarketDataHubV2()
            ),
        )
    )

    bundle = runtime(
        "FYERS"
    )

    orchestrator.install_runtime(
        bundle
    )

    orchestrator.acquire_runtime(
        provider="FYERS",
        consumer_id="NIFTY_ENGINE",
    )

    orchestrator.release_runtime(
        provider="FYERS",
        consumer_id="NIFTY_ENGINE",
    )

    orchestrator.close_provider(
        "FYERS"
    )

    assert (
        bundle.streaming.close_calls
        == 1
    )

    assert not orchestrator.is_runtime_installed(
        "FYERS"
    )


def test_p44e_contains_no_provider_sdk_auth_or_order_authority():
    paths = (
        Path(
            "services/contracts/"
            "provider_runtime_bundle_v2.py"
        ),
        Path(
            "services/broker/"
            "shared_provider_orchestrator_v2.py"
        ),
    )

    text = "\n".join(
        path.read_text(
            encoding="utf-8",
        )
        for path in paths
    )

    forbidden = (
        "SmartConnect",
        "fyers_apiv3",
        "generateSession",
        "access_token",
        "FYERS_SECRET_KEY",
        "ANGEL_API_KEY",
        "place_order",
        "placeOrder(",
        "submit_order",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]

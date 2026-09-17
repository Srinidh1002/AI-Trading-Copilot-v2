"""FYERS V2 read-only runtime composition.

F10 composes the independently proven F7/F8/F9 capabilities into one
ProviderRuntimeBundleV2. Credentials, environment loading and SDK construction
remain outside this module. No order capability or automatic fallback exists
here.
"""

from __future__ import annotations

from services.broker.fyers_five_market_resolver_v2 import (
    FyersFiveMarketInstrumentResolverV2,
)
from services.broker.fyers_provider_adapters_v2 import (
    FyersHistoricalDataProviderV2,
    FyersQuoteDepthProviderV2,
    FyersRequestControllerV2,
)
from services.broker.provider_data_interfaces_v2 import (
    StreamingMarketDataProviderV2,
)
from services.contracts.provider_runtime_bundle_v2 import (
    ProviderRequestControllerV2,
    ProviderRuntimeBundleV2,
)


class FyersRuntimeCompositionError(RuntimeError):
    """FYERS runtime composition failed closed."""


def _assert_streaming_safety(streaming) -> None:
    if not isinstance(streaming, StreamingMarketDataProviderV2):
        raise TypeError(
            "streaming does not satisfy StreamingMarketDataProviderV2"
        )

    if getattr(streaming, "data_only", None) is not True:
        raise FyersRuntimeCompositionError(
            "FYERS streaming must remain data-only"
        )

    if getattr(streaming, "order_capability_allowed", None) is not False:
        raise FyersRuntimeCompositionError(
            "FYERS streaming order capability is prohibited"
        )

    if getattr(streaming, "automatic_fallback_allowed", None) is not False:
        raise FyersRuntimeCompositionError(
            "FYERS streaming automatic fallback is prohibited"
        )


def build_fyers_provider_runtime_v2(
    *,
    data_client,
    streaming,
    master_store=None,
    clock=None,
    request_controller: ProviderRequestControllerV2 | None = None,
) -> ProviderRuntimeBundleV2:
    """Build one shared FYERS data-only runtime bundle.

    The caller supplies an already-created data-only REST client and the F9
    streaming adapter. This function performs no authentication, environment
    reads, network requests, order calls or fallback selection.
    """

    if data_client is None:
        raise ValueError("data_client is required")

    _assert_streaming_safety(streaming)

    controller = request_controller or FyersRequestControllerV2()
    if not isinstance(controller, ProviderRequestControllerV2):
        raise TypeError(
            "request_controller does not satisfy ProviderRequestControllerV2"
        )

    resolver = FyersFiveMarketInstrumentResolverV2(
        data_client=data_client,
        master_store=master_store,
        clock=clock,
    )

    return ProviderRuntimeBundleV2(
        provider="FYERS",
        resolver=resolver,
        historical=FyersHistoricalDataProviderV2(data_client),
        quote_depth=FyersQuoteDepthProviderV2(data_client),
        streaming=streaming,
        request_controller=controller,
    )

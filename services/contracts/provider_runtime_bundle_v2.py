"""Provider-neutral bundle of one provider's shared read-only runtime capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from services.broker.provider_data_interfaces_v2 import (
    HistoricalDataProviderV2,
    InstrumentResolverV2,
    QuoteDepthProviderV2,
    StreamingMarketDataProviderV2,
)
from services.broker.provider_registry_v2 import (
    get_provider_registration,
)


@runtime_checkable
class ProviderRequestControllerV2(Protocol):
    """Structural contract satisfied by provider-specific pacing controllers."""

    def wait_for_slot(
        self,
        request_type,
        attempt,
    ):
        ...

    def record_rate_limit(
        self,
        request_type,
        retry_number,
        backoff_multiplier,
    ):
        ...

    def record_success(
        self,
        request_type,
    ):
        ...


@dataclass(frozen=True, slots=True)
class ProviderRuntimeBundleV2:
    """Exactly one shared capability bundle for one provider."""

    provider: str

    resolver: InstrumentResolverV2
    historical: HistoricalDataProviderV2
    quote_depth: QuoteDepthProviderV2
    streaming: StreamingMarketDataProviderV2
    request_controller: ProviderRequestControllerV2

    data_only: bool = True
    order_capability_allowed: bool = False
    automatic_fallback_allowed: bool = False

    schema_version: str = (
        "provider_runtime_bundle.v2"
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.provider,
            str,
        ):
            raise ValueError(
                "Provider is required."
            )

        provider = (
            self.provider
            .strip()
            .upper()
        )

        registration = (
            get_provider_registration(
                provider
            )
        )

        if registration.data_only is not True:
            raise ValueError(
                "Provider registration is not data-only."
            )

        if not isinstance(
            self.resolver,
            InstrumentResolverV2,
        ):
            raise TypeError(
                "Resolver does not satisfy InstrumentResolverV2."
            )

        if not isinstance(
            self.historical,
            HistoricalDataProviderV2,
        ):
            raise TypeError(
                "Historical adapter does not satisfy HistoricalDataProviderV2."
            )

        if not isinstance(
            self.quote_depth,
            QuoteDepthProviderV2,
        ):
            raise TypeError(
                "Quote/depth adapter does not satisfy QuoteDepthProviderV2."
            )

        if not isinstance(
            self.streaming,
            StreamingMarketDataProviderV2,
        ):
            raise TypeError(
                "Streaming adapter does not satisfy StreamingMarketDataProviderV2."
            )

        if not isinstance(
            self.request_controller,
            ProviderRequestControllerV2,
        ):
            raise TypeError(
                "Request controller does not satisfy ProviderRequestControllerV2."
            )

        if self.data_only is not True:
            raise ValueError(
                "Provider runtime must remain data-only."
            )

        if self.order_capability_allowed is not False:
            raise ValueError(
                "Order capability is prohibited."
            )

        if self.automatic_fallback_allowed is not False:
            raise ValueError(
                "Automatic fallback is prohibited."
            )

        if (
            self.schema_version
            != "provider_runtime_bundle.v2"
        ):
            raise ValueError(
                "Invalid provider runtime schema."
            )

        object.__setattr__(
            self,
            "provider",
            provider,
        )

"""Shared ownership of provider runtimes for the five-market data architecture.

This layer does not authenticate, create SDK clients, choose a fallback
provider, or perform market requests by itself. Provider adapters are
installed explicitly by later integration phases.
"""

from __future__ import annotations

from collections.abc import (
    Callable,
    Sequence,
)
from threading import RLock

from services.broker.provider_registry_v2 import (
    get_provider_registration,
)
from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.contracts.market_data_v2 import (
    ProviderHealthV2,
)
from services.contracts.provider_runtime_bundle_v2 import (
    ProviderRuntimeBundleV2,
)
from services.core.provider_routing_policy_v2 import (
    resolve_operational_primary,
)


class ProviderRuntimeUnavailableError(
    RuntimeError
):
    pass


class ProviderRuntimeAlreadyInstalledError(
    RuntimeError
):
    pass


class ProviderRuntimeInUseError(
    RuntimeError
):
    pass


def _provider(
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            "Provider is required."
        )

    value = (
        value
        .strip()
        .upper()
    )

    get_provider_registration(
        value
    )

    return value


def _consumer(
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            "Consumer id is required."
        )

    value = value.strip()

    if not value:
        raise ValueError(
            "Consumer id is required."
        )

    return value


class SharedProviderOrchestratorV2:
    """Own one runtime bundle per provider and share it across consumers."""

    def __init__(
        self,
        *,
        market_data_hub: SharedMarketDataHubV2,
    ) -> None:
        if not isinstance(
            market_data_hub,
            SharedMarketDataHubV2,
        ):
            raise TypeError(
                "market_data_hub must be SharedMarketDataHubV2."
            )

        self._hub = market_data_hub
        self._lock = RLock()

        self._runtimes: dict[
            str,
            ProviderRuntimeBundleV2,
        ] = {}

        self._consumers: dict[
            str,
            set[str],
        ] = {}

        self._subscriptions: dict[
            tuple[str, str],
            str,
        ] = {}

    def install_runtime(
        self,
        runtime: ProviderRuntimeBundleV2,
    ) -> None:
        if not isinstance(
            runtime,
            ProviderRuntimeBundleV2,
        ):
            raise TypeError(
                "Expected ProviderRuntimeBundleV2."
            )

        provider = runtime.provider

        with self._lock:
            if provider in self._runtimes:
                raise ProviderRuntimeAlreadyInstalledError(
                    "PROVIDER_RUNTIME_ALREADY_INSTALLED"
                )

            self._runtimes[
                provider
            ] = runtime

            self._consumers[
                provider
            ] = set()

    def is_runtime_installed(
        self,
        provider: str,
    ) -> bool:
        provider = _provider(
            provider
        )

        with self._lock:
            return provider in self._runtimes

    def get_explicit_runtime(
        self,
        provider: str,
    ) -> ProviderRuntimeBundleV2:
        """Return only the explicitly requested provider; never substitute."""

        provider = _provider(
            provider
        )

        with self._lock:
            runtime = (
                self._runtimes.get(
                    provider
                )
            )

        if runtime is None:
            raise ProviderRuntimeUnavailableError(
                "PROVIDER_RUNTIME_UNAVAILABLE"
            )

        return runtime

    def acquire_runtime(
        self,
        *,
        provider: str,
        consumer_id: str,
    ) -> ProviderRuntimeBundleV2:
        """Lease the same provider runtime to another consumer."""

        provider = _provider(
            provider
        )

        consumer_id = _consumer(
            consumer_id
        )

        runtime = (
            self.get_explicit_runtime(
                provider
            )
        )

        with self._lock:
            self._consumers[
                provider
            ].add(
                consumer_id
            )

        return runtime

    def release_runtime(
        self,
        *,
        provider: str,
        consumer_id: str,
    ) -> None:
        provider = _provider(
            provider
        )

        consumer_id = _consumer(
            consumer_id
        )

        with self._lock:
            consumers = (
                self._consumers.get(
                    provider
                )
            )

            if consumers is None:
                raise ProviderRuntimeUnavailableError(
                    "PROVIDER_RUNTIME_UNAVAILABLE"
                )

            if (
                (
                    provider,
                    consumer_id,
                )
                in self._subscriptions
            ):
                raise ProviderRuntimeInUseError(
                    "CONSUMER_STREAM_SUBSCRIPTION_ACTIVE"
                )

            consumers.discard(
                consumer_id
            )

    def get_operational_primary_runtime(
        self,
        *,
        market_symbol: str,
        data_kind: str,
        consumer_id: str,
    ) -> ProviderRuntimeBundleV2:
        """Resolve only an explicitly READY primary route."""

        provider = (
            resolve_operational_primary(
                market_symbol,
                data_kind,
            )
        )

        return self.acquire_runtime(
            provider=provider,
            consumer_id=consumer_id,
        )

    def subscribe(
        self,
        *,
        provider: str,
        consumer_id: str,
        instruments: Sequence,
        callback: Callable,
    ) -> str:
        """Use the provider's single installed streaming-adapter instance."""

        provider = _provider(
            provider
        )

        consumer_id = _consumer(
            consumer_id
        )

        if not callable(
            callback
        ):
            raise TypeError(
                "callback must be callable."
            )

        runtime = self.acquire_runtime(
            provider=provider,
            consumer_id=consumer_id,
        )

        key = (
            provider,
            consumer_id,
        )

        with self._lock:
            if key in self._subscriptions:
                raise ProviderRuntimeInUseError(
                    "CONSUMER_ALREADY_SUBSCRIBED"
                )

        subscription_id = (
            runtime.streaming.subscribe(
                instruments,
                callback,
            )
        )

        if (
            not isinstance(
                subscription_id,
                str,
            )
            or not subscription_id.strip()
        ):
            raise RuntimeError(
                "INVALID_PROVIDER_SUBSCRIPTION_ID"
            )

        subscription_id = (
            subscription_id.strip()
        )

        with self._lock:
            self._subscriptions[
                key
            ] = subscription_id

        return subscription_id

    def unsubscribe(
        self,
        *,
        provider: str,
        consumer_id: str,
    ) -> None:
        provider = _provider(
            provider
        )

        consumer_id = _consumer(
            consumer_id
        )

        key = (
            provider,
            consumer_id,
        )

        runtime = (
            self.get_explicit_runtime(
                provider
            )
        )

        with self._lock:
            subscription_id = (
                self._subscriptions.get(
                    key
                )
            )

        if subscription_id is None:
            raise ProviderRuntimeUnavailableError(
                "STREAM_SUBSCRIPTION_UNAVAILABLE"
            )

        runtime.streaming.unsubscribe(
            subscription_id
        )

        with self._lock:
            self._subscriptions.pop(
                key,
                None,
            )

    def publish_provider_health(
        self,
        health: ProviderHealthV2,
    ) -> None:
        if not isinstance(
            health,
            ProviderHealthV2,
        ):
            raise TypeError(
                "Expected ProviderHealthV2."
            )

        _provider(
            health.provider
        )

        self._hub.set_provider_health(
            health
        )

    def close_provider(
        self,
        provider: str,
    ) -> None:
        """Close only an unused provider runtime."""

        provider = _provider(
            provider
        )

        runtime = (
            self.get_explicit_runtime(
                provider
            )
        )

        with self._lock:
            consumers = set(
                self._consumers.get(
                    provider,
                    set(),
                )
            )

            subscriptions = [
                key
                for key
                in self._subscriptions
                if key[0] == provider
            ]

        if consumers or subscriptions:
            raise ProviderRuntimeInUseError(
                "PROVIDER_RUNTIME_IN_USE"
            )

        runtime.streaming.close()

        with self._lock:
            self._runtimes.pop(
                provider,
                None,
            )

            self._consumers.pop(
                provider,
                None,
            )

    def snapshot(
        self,
    ) -> dict[str, object]:
        with self._lock:
            return {
                "providers": tuple(
                    sorted(
                        self._runtimes
                    )
                ),
                "consumer_counts": {
                    provider: len(
                        consumers
                    )
                    for (
                        provider,
                        consumers,
                    )
                    in self._consumers.items()
                },
                "subscription_count": len(
                    self._subscriptions
                ),
            }

"""Planned provider routing policy for the five-market data architecture.

Routing is intentionally non-operational until the relevant V2 adapter is
marked READY. There is no automatic or silent provider fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.broker.provider_registry_v2 import (
    assert_provider_adapter_ready,
    get_provider_registration,
)
from services.core.five_market_universe_v2 import (
    get_target_market,
)


_DATA_KINDS = {
    "INSTRUMENT",
    "QUOTE",
    "DEPTH",
    "HISTORICAL",
    "STREAMING",
}


@dataclass(frozen=True, slots=True)
class ProviderRouteV2:
    market_symbol: str
    data_kind: str
    primary_provider: str
    shadow_providers: tuple[str, ...]
    routing_status: str = "PLANNED"
    fallback_mode: str = "FAIL_CLOSED"
    automatic_fallback_allowed: bool = False
    comparison_enabled: bool = True
    schema_version: str = "provider_route.v2"

    def __post_init__(self) -> None:
        market = get_target_market(
            self.market_symbol
        )

        data_kind = (
            self.data_kind.strip().upper()
            if isinstance(
                self.data_kind,
                str,
            )
            else ""
        )

        if data_kind not in _DATA_KINDS:
            raise ValueError(
                "Unsupported provider data kind."
            )

        primary = (
            self.primary_provider.strip().upper()
            if isinstance(
                self.primary_provider,
                str,
            )
            else ""
        )

        primary_registration = (
            get_provider_registration(
                primary
            )
        )

        if primary_registration.role != "PRIMARY":
            raise ValueError(
                "Route primary must use PRIMARY provider."
            )

        if not isinstance(
            self.shadow_providers,
            tuple,
        ):
            raise ValueError(
                "Shadow providers must be a tuple."
            )

        shadows = tuple(
            str(provider).strip().upper()
            for provider
            in self.shadow_providers
        )

        if not shadows:
            raise ValueError(
                "Shadow provider is required for parity validation."
            )

        if primary in shadows:
            raise ValueError(
                "Primary cannot also be shadow."
            )

        if len(set(shadows)) != len(shadows):
            raise ValueError(
                "Duplicate shadow provider."
            )

        for provider in shadows:
            registration = (
                get_provider_registration(
                    provider
                )
            )

            if registration.role != "SHADOW":
                raise ValueError(
                    "Shadow route requires SHADOW provider."
                )

        if self.routing_status != "PLANNED":
            raise ValueError(
                "P4.4D routes must remain PLANNED."
            )

        if self.fallback_mode != "FAIL_CLOSED":
            raise ValueError(
                "Provider routing must fail closed."
            )

        if self.automatic_fallback_allowed is not False:
            raise ValueError(
                "Automatic provider fallback is prohibited."
            )

        if self.comparison_enabled is not True:
            raise ValueError(
                "Shadow comparison must remain enabled."
            )

        if (
            self.schema_version
            != "provider_route.v2"
        ):
            raise ValueError(
                "Invalid provider-route schema."
            )

        object.__setattr__(
            self,
            "market_symbol",
            market.symbol,
        )

        object.__setattr__(
            self,
            "data_kind",
            data_kind,
        )

        object.__setattr__(
            self,
            "primary_provider",
            primary,
        )

        object.__setattr__(
            self,
            "shadow_providers",
            shadows,
        )


_PLANNED_ROUTES = tuple(
    ProviderRouteV2(
        market_symbol=market_symbol,
        data_kind=data_kind,
        primary_provider="FYERS",
        shadow_providers=(
            "ANGEL_SMARTAPI",
        ),
    )
    for market_symbol in (
        "NIFTY",
        "SENSEX",
        "CRUDEOILM",
        "GOLDM",
        "SILVERM",
    )
    for data_kind in (
        "INSTRUMENT",
        "QUOTE",
        "DEPTH",
        "HISTORICAL",
        "STREAMING",
    )
)


_ROUTE_INDEX = {
    (
        route.market_symbol,
        route.data_kind,
    ): route
    for route in _PLANNED_ROUTES
}


def list_planned_routes(
) -> tuple[ProviderRouteV2, ...]:
    return _PLANNED_ROUTES


def get_planned_route(
    market_symbol: str,
    data_kind: str,
) -> ProviderRouteV2:
    market = get_target_market(
        market_symbol
    )

    if not isinstance(
        data_kind,
        str,
    ):
        raise ValueError(
            "Data kind is required."
        )

    key = (
        market.symbol,
        data_kind.strip().upper(),
    )

    try:
        return _ROUTE_INDEX[
            key
        ]
    except KeyError as exc:
        raise ValueError(
            "No planned provider route."
        ) from exc


def resolve_operational_primary(
    market_symbol: str,
    data_kind: str,
) -> str:
    """Return primary only when its V2 adapter is explicitly READY."""

    route = get_planned_route(
        market_symbol,
        data_kind,
    )

    assert_provider_adapter_ready(
        route.primary_provider
    )

    return route.primary_provider


def resolve_shadow_providers(
    market_symbol: str,
    data_kind: str,
    *,
    require_ready: bool = True,
) -> tuple[str, ...]:
    route = get_planned_route(
        market_symbol,
        data_kind,
    )

    if require_ready:
        for provider in (
            route.shadow_providers
        ):
            assert_provider_adapter_ready(
                provider
            )

    return route.shadow_providers


def automatic_fallback_provider(
    market_symbol: str,
    data_kind: str,
) -> None:
    """Deliberately never returns a substitute provider."""

    get_planned_route(
        market_symbol,
        data_kind,
    )

    return None

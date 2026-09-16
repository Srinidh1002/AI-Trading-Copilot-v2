"""Provider registry for the planned five-market read-only data architecture.

This module declares provider identity and V2 adapter readiness only.
It performs no authentication, SDK import, network request or fallback.
"""

from __future__ import annotations

from dataclasses import dataclass


_CAPABILITIES = {
    "INSTRUMENT_RESOLUTION",
    "QUOTE",
    "DEPTH",
    "HISTORICAL",
    "STREAMING",
}

_ROLES = {
    "PRIMARY",
    "SHADOW",
}

_ADAPTER_STATUSES = {
    "PENDING_V2_ADAPTER",
    "READY",
    "DISABLED",
}


@dataclass(frozen=True, slots=True)
class ProviderRegistrationV2:
    provider: str
    role: str
    priority: int
    intended_capabilities: tuple[str, ...]
    adapter_status: str
    data_only: bool = True
    order_capability_allowed: bool = False
    automatic_fallback_allowed: bool = False
    schema_version: str = "provider_registration.v2"

    def __post_init__(self) -> None:
        provider = (
            self.provider.strip().upper()
            if isinstance(
                self.provider,
                str,
            )
            else ""
        )

        role = (
            self.role.strip().upper()
            if isinstance(
                self.role,
                str,
            )
            else ""
        )

        adapter_status = (
            self.adapter_status.strip().upper()
            if isinstance(
                self.adapter_status,
                str,
            )
            else ""
        )

        if provider not in {
            "FYERS",
            "ANGEL_SMARTAPI",
        }:
            raise ValueError(
                "Unsupported V2 provider."
            )

        if role not in _ROLES:
            raise ValueError(
                "Invalid provider role."
            )

        if (
            not isinstance(
                self.priority,
                int,
            )
            or isinstance(
                self.priority,
                bool,
            )
            or self.priority < 1
        ):
            raise ValueError(
                "Invalid provider priority."
            )

        if not isinstance(
            self.intended_capabilities,
            tuple,
        ):
            raise ValueError(
                "Capabilities must be a tuple."
            )

        capabilities = tuple(
            str(value).strip().upper()
            for value
            in self.intended_capabilities
        )

        if (
            not capabilities
            or len(set(capabilities))
            != len(capabilities)
            or any(
                value not in _CAPABILITIES
                for value in capabilities
            )
        ):
            raise ValueError(
                "Invalid provider capability set."
            )

        if adapter_status not in _ADAPTER_STATUSES:
            raise ValueError(
                "Invalid V2 adapter status."
            )

        if self.data_only is not True:
            raise ValueError(
                "Provider registry is data-only."
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
            != "provider_registration.v2"
        ):
            raise ValueError(
                "Invalid provider-registration schema."
            )

        object.__setattr__(
            self,
            "provider",
            provider,
        )

        object.__setattr__(
            self,
            "role",
            role,
        )

        object.__setattr__(
            self,
            "adapter_status",
            adapter_status,
        )

        object.__setattr__(
            self,
            "intended_capabilities",
            capabilities,
        )


_REQUIRED_CAPABILITIES = (
    "INSTRUMENT_RESOLUTION",
    "QUOTE",
    "DEPTH",
    "HISTORICAL",
    "STREAMING",
)


PROVIDER_REGISTRY_V2 = (
    ProviderRegistrationV2(
        provider="FYERS",
        role="PRIMARY",
        priority=1,
        intended_capabilities=(
            _REQUIRED_CAPABILITIES
        ),
        adapter_status=(
            "PENDING_V2_ADAPTER"
        ),
    ),
    ProviderRegistrationV2(
        provider="ANGEL_SMARTAPI",
        role="SHADOW",
        priority=2,
        intended_capabilities=(
            _REQUIRED_CAPABILITIES
        ),
        adapter_status=(
            "PENDING_V2_ADAPTER"
        ),
    ),
)


_BY_PROVIDER = {
    item.provider: item
    for item in PROVIDER_REGISTRY_V2
}


def list_provider_registrations(
) -> tuple[ProviderRegistrationV2, ...]:
    return PROVIDER_REGISTRY_V2


def get_provider_registration(
    provider: str,
) -> ProviderRegistrationV2:
    if not isinstance(
        provider,
        str,
    ):
        raise ValueError(
            "Provider is required."
        )

    provider = provider.strip().upper()

    try:
        return _BY_PROVIDER[
            provider
        ]
    except KeyError as exc:
        raise ValueError(
            "Unknown V2 provider."
        ) from exc


def provider_adapter_ready(
    provider: str,
) -> bool:
    return (
        get_provider_registration(
            provider
        ).adapter_status
        == "READY"
    )


def assert_provider_adapter_ready(
    provider: str,
) -> ProviderRegistrationV2:
    registration = (
        get_provider_registration(
            provider
        )
    )

    if registration.adapter_status != "READY":
        raise RuntimeError(
            "PROVIDER_V2_ADAPTER_NOT_READY"
        )

    return registration

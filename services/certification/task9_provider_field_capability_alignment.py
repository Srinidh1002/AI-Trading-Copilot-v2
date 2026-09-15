"""Cross-authority consistency validation for Task 9 provider field capabilities.

This module owns no provider facts.  It only verifies that the static
field-capability registry, Angel-specific capability authority, and generic
Task 9 provider report cannot contradict one another.
"""
from __future__ import annotations

from services.certification.task9_angel_provider_capability_bridge import (
    validate_task9_angel_generic_capability_alignment,
)
from services.contracts.provider_capability_registry_v1 import (
    ProviderCapabilityRegistryV1,
)
from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
    Task9AngelCapabilitySessionV1,
    Task9AngelRequirement,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderCapability,
    Task9ProviderCapabilityReportV1,
    Task9ProviderFamily,
    Task9ProviderReadinessStatus,
    Task9ProviderSupportStatus,
)


_IDENTITIES = (
    ("NIFTY", "NSE", "NFO"),
    ("SENSEX", "BSE", "BFO"),
)

_OPTION_FULL_FIELDS = (
    "option_universe",
    "premium_ltp",
    "oi",
    "volume",
    "bid",
    "ask",
)

_CANDLE_FIELDS = (
    "5m_candles",
    "15m_candles",
    "1h_candles",
    "1d_candles",
)


def _generic_state(
    report: Task9ProviderCapabilityReportV1,
    *,
    family: Task9ProviderFamily,
    capability: Task9ProviderCapability,
    market: str | None = None,
    exchange: str | None = None,
):
    matches = tuple(
        state
        for state in report.capability_states
        if (
            state.provider_family is family
            and state.capability is capability
            and state.market == market
            and state.exchange == exchange
        )
    )

    if len(matches) != 1:
        raise ValueError(
            "TASK9_FIELD_GENERIC_CAPABILITY_IDENTITY_INVALID:"
            f"{family.value}:{capability.value}:"
            f"{market}:{exchange}"
        )

    return matches[0]


def _require_runtime_provider_capability(
    state,
    *,
    label: str,
) -> None:
    if state.required is not True:
        raise ValueError(
            "TASK9_FIELD_REQUIRED_RUNTIME_CAPABILITY_MISMATCH:"
            + label
        )

    if (
        state.documentation_status
        is Task9ProviderSupportStatus.UNSUPPORTED
        or state.implementation_status
        is Task9ProviderSupportStatus.UNSUPPORTED
        or state.readiness_status
        is Task9ProviderReadinessStatus.UNSUPPORTED
    ):
        raise ValueError(
            "TASK9_FIELD_SUPPORTED_RUNTIME_CAPABILITY_MISMATCH:"
            + label
        )


def validate_task9_provider_field_runtime_alignment(
    *,
    registry: ProviderCapabilityRegistryV1,
    angel: Task9AngelCapabilitySessionV1,
    generic: Task9ProviderCapabilityReportV1,
) -> None:
    if type(registry) is not ProviderCapabilityRegistryV1:
        raise TypeError("registry")

    if type(angel) is not Task9AngelCapabilitySessionV1:
        raise TypeError("angel")

    if type(generic) is not Task9ProviderCapabilityReportV1:
        raise TypeError("generic")

    # First preserve the already-certified Angel-specific -> generic
    # capability alignment authority.
    validate_task9_angel_generic_capability_alignment(
        angel=angel,
        generic=generic,
    )

    for (
        market,
        spot_exchange,
        option_exchange,
    ) in _IDENTITIES:
        spot_static = registry.state(
            market,
            spot_exchange,
            option_exchange,
            "spot",
        )

        timestamp_static = registry.state(
            market,
            spot_exchange,
            option_exchange,
            "provider_timestamp",
        )

        if (
            spot_static != "SUPPORTED"
            or timestamp_static != "SUPPORTED"
        ):
            raise ValueError(
                "TASK9_FIELD_SPOT_STATIC_CAPABILITY_MISMATCH:"
                + market
            )

        spot_runtime = _generic_state(
            generic,
            family=Task9ProviderFamily.ANGEL_SPOT,
            capability=(
                Task9ProviderCapability.SPOT_QUOTES
            ),
            market=market,
            exchange=spot_exchange,
        )

        _require_runtime_provider_capability(
            spot_runtime,
            label=f"{market}:SPOT_QUOTES",
        )

        for field in _OPTION_FULL_FIELDS:
            if (
                registry.state(
                    market,
                    spot_exchange,
                    option_exchange,
                    field,
                )
                != "SUPPORTED"
            ):
                raise ValueError(
                    "TASK9_FIELD_OPTION_FULL_STATIC_CAPABILITY_MISMATCH:"
                    f"{market}:{field}"
                )

        option_full_runtime = _generic_state(
            generic,
            family=(
                Task9ProviderFamily.ANGEL_OPTION_FULL
            ),
            capability=(
                Task9ProviderCapability.OPTION_FULL_QUOTES
            ),
            market=market,
            exchange=option_exchange,
        )

        _require_runtime_provider_capability(
            option_full_runtime,
            label=f"{market}:OPTION_FULL_QUOTES",
        )

        if (
            registry.state(
                market,
                spot_exchange,
                option_exchange,
                "provider_oi_change",
            )
            != "UNSUPPORTED"
        ):
            raise ValueError(
                "TASK9_FIELD_NATIVE_OI_STATIC_CAPABILITY_MISMATCH:"
                + market
            )

        if (
            registry.state(
                market,
                spot_exchange,
                option_exchange,
                "derived_oi_change",
            )
            != "DERIVED"
        ):
            raise ValueError(
                "TASK9_FIELD_DERIVED_OI_STATIC_CAPABILITY_MISMATCH:"
                + market
            )

        if (
            registry.state(
                market,
                spot_exchange,
                option_exchange,
                "spread",
            )
            != "DERIVED"
        ):
            raise ValueError(
                "TASK9_FIELD_SPREAD_STATIC_CAPABILITY_MISMATCH:"
                + market
            )

        for field in _CANDLE_FIELDS:
            if (
                registry.state(
                    market,
                    spot_exchange,
                    option_exchange,
                    field,
                )
                != "UNVERIFIED_LIVE"
            ):
                raise ValueError(
                    "TASK9_FIELD_CANDLE_CAPABILITY_PREMATURE_PROMOTION:"
                    f"{market}:{field}"
                )

        if (
            registry.state(
                market,
                spot_exchange,
                option_exchange,
                "india_vix_applicability",
            )
            != "OPTIONAL"
        ):
            raise ValueError(
                "TASK9_FIELD_VIX_STATIC_CAPABILITY_MISMATCH:"
                + market
            )

    native_oi = _generic_state(
        generic,
        family=(
            Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET
        ),
        capability=(
            Task9ProviderCapability.PROVIDER_NATIVE_OI_CHANGE
        ),
    )

    if (
        native_oi.required
        or native_oi.documentation_status
        is not Task9ProviderSupportStatus.UNSUPPORTED
        or native_oi.implementation_status
        is not Task9ProviderSupportStatus.UNSUPPORTED
        or native_oi.live_proof_status
        is not Task9LiveProofStatus.NOT_APPLICABLE
        or native_oi.readiness_status
        is not Task9ProviderReadinessStatus.UNSUPPORTED
    ):
        raise ValueError(
            "TASK9_FIELD_NATIVE_OI_RUNTIME_CAPABILITY_MISMATCH"
        )

    derived_oi = _generic_state(
        generic,
        family=(
            Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET
        ),
        capability=(
            Task9ProviderCapability.TASK9_DERIVED_OI_CHANGE
        ),
    )

    if (
        derived_oi.required
        or derived_oi.live_proof_status
        is not Task9LiveProofStatus.PROVEN
        or derived_oi.readiness_status
        is not Task9ProviderReadinessStatus.READY
        or derived_oi.startup_semantic is not None
    ):
        raise ValueError(
            "TASK9_FIELD_DERIVED_OI_RUNTIME_CAPABILITY_MISMATCH"
        )

    vix = _generic_state(
        generic,
        family=Task9ProviderFamily.INDIA_VIX,
        capability=Task9ProviderCapability.INDIA_VIX,
    )

    if vix.required:
        raise ValueError(
            "TASK9_FIELD_VIX_MUST_REMAIN_OPTIONAL"
        )

    nifty_greeks = angel.capability(
        Task9AngelCapability.NFO_OPTION_GREEKS
    )

    if (
        registry.state(
            "NIFTY",
            "NSE",
            "NFO",
            "greeks",
        )
        != "SUPPORTED"
        or nifty_greeks.requirement
        is not Task9AngelRequirement.OPTIONAL
        or nifty_greeks.documentation_status
        is Task9ProviderSupportStatus.UNSUPPORTED
    ):
        raise ValueError(
            "TASK9_FIELD_NFO_GREEKS_ALIGNMENT_MISMATCH"
        )

    sensex_greeks = angel.capability(
        Task9AngelCapability.BFO_OPTION_GREEKS
    )

    if (
        registry.state(
            "SENSEX",
            "BSE",
            "BFO",
            "greeks",
        )
        != "UNSUPPORTED"
        or sensex_greeks.requirement
        is not Task9AngelRequirement.OPTIONAL
        or sensex_greeks.documentation_status
        is not Task9ProviderSupportStatus.UNSUPPORTED
        or sensex_greeks.live_proof_status
        is not Task9LiveProofStatus.NOT_APPLICABLE
        or sensex_greeks.readiness_status
        is not Task9ProviderReadinessStatus.UNSUPPORTED
    ):
        raise ValueError(
            "TASK9_FIELD_BFO_GREEKS_ALIGNMENT_MISMATCH"
        )

    # IV remains intentionally field-registry-owned in this slice.
    # Do not invent a generic IV capability or silently map IV to the
    # Greeks endpoint without explicit provider/source authority.
    if (
        registry.state(
            "NIFTY",
            "NSE",
            "NFO",
            "iv",
        )
        != "SUPPORTED"
        or registry.state(
            "SENSEX",
            "BSE",
            "BFO",
            "iv",
        )
        != "UNSUPPORTED"
    ):
        raise ValueError(
            "TASK9_FIELD_IV_STATIC_CAPABILITY_MISMATCH"
        )


__all__ = (
    "validate_task9_provider_field_runtime_alignment",
)

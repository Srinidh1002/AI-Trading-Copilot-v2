"""Bridge Task9 Angel-specific capability authority into generic provider readiness."""
from __future__ import annotations

from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
    Task9AngelCapabilitySessionV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9ProviderCapability,
    Task9ProviderCapabilityReportV1,
    Task9ProviderFamily,
    Task9ProviderReadinessStatus,
)


_ANGEL_TO_GENERIC = {
    Task9AngelCapability.AUTH_SESSION: (
        Task9ProviderFamily.ANGEL_AUTH_SESSION,
        Task9ProviderCapability.AUTH_SESSION,
        None,
        None,
    ),
    Task9AngelCapability.INSTRUMENT_MASTER: (
        Task9ProviderFamily.ANGEL_INSTRUMENT_MASTER,
        Task9ProviderCapability.INSTRUMENT_MASTER,
        None,
        None,
    ),
    Task9AngelCapability.NIFTY_SPOT_FULL: (
        Task9ProviderFamily.ANGEL_SPOT,
        Task9ProviderCapability.SPOT_QUOTES,
        "NIFTY",
        "NSE",
    ),
    Task9AngelCapability.SENSEX_SPOT_FULL: (
        Task9ProviderFamily.ANGEL_SPOT,
        Task9ProviderCapability.SPOT_QUOTES,
        "SENSEX",
        "BSE",
    ),
    Task9AngelCapability.NFO_OPTION_FULL: (
        Task9ProviderFamily.ANGEL_OPTION_FULL,
        Task9ProviderCapability.OPTION_FULL_QUOTES,
        "NIFTY",
        "NFO",
    ),
    Task9AngelCapability.BFO_OPTION_FULL: (
        Task9ProviderFamily.ANGEL_OPTION_FULL,
        Task9ProviderCapability.OPTION_FULL_QUOTES,
        "SENSEX",
        "BFO",
    ),
    Task9AngelCapability.NFO_OPTION_GREEKS: (
        Task9ProviderFamily.ANGEL_OPTION_GREEKS,
        Task9ProviderCapability.OPTION_GREEKS,
        "NIFTY",
        "NFO",
    ),
    Task9AngelCapability.BFO_OPTION_GREEKS: (
        Task9ProviderFamily.ANGEL_OPTION_GREEKS,
        Task9ProviderCapability.OPTION_GREEKS,
        "SENSEX",
        "BFO",
    ),
    Task9AngelCapability.INDIA_VIX: (
        Task9ProviderFamily.INDIA_VIX,
        Task9ProviderCapability.INDIA_VIX,
        None,
        None,
    ),
}


def validate_task9_angel_generic_capability_alignment(
    *,
    angel: Task9AngelCapabilitySessionV1,
    generic: Task9ProviderCapabilityReportV1,
) -> None:
    if type(angel) is not Task9AngelCapabilitySessionV1:
        raise TypeError("angel")

    if type(generic) is not Task9ProviderCapabilityReportV1:
        raise TypeError("generic")

    generic_index = {
        (
            state.provider_family,
            state.capability,
            state.market,
            state.exchange,
        ): state
        for state in generic.capability_states
    }

    for angel_capability, generic_identity in (
        _ANGEL_TO_GENERIC.items()
    ):
        angel_state = angel.capability(
            angel_capability
        )

        generic_state = generic_index.get(
            generic_identity
        )
        if generic_state is None:
            raise ValueError(
                "TASK9_ANGEL_GENERIC_CAPABILITY_MISSING:"
                f"{angel_capability.value}"
            )

        if (
            angel_state.live_proof_status
            != generic_state.live_proof_status
        ):
            raise ValueError(
                "TASK9_ANGEL_GENERIC_LIVE_PROOF_MISMATCH:"
                f"{angel_capability.value}"
            )

        if (
            angel_state.readiness_status
            != generic_state.readiness_status
        ):
            raise ValueError(
                "TASK9_ANGEL_GENERIC_READINESS_MISMATCH:"
                f"{angel_capability.value}"
            )

        expected_market = generic_identity[2]
        expected_exchange = generic_identity[3]

        if (
            expected_market is not None
            and (
                angel_state.market != expected_market
                or angel_state.exchange != expected_exchange
                or generic_state.market != expected_market
                or generic_state.exchange != expected_exchange
            )
        ):
            raise ValueError(
                "TASK9_ANGEL_GENERIC_IDENTITY_MISMATCH:"
                f"{angel_capability.value}"
            )

    # Request-budget authority is Angel-specific operational
    # infrastructure and has no separate generic 9.82 row.
    budget = angel.capability(
        Task9AngelCapability.REQUEST_BUDGET
    )
    if (
        budget.readiness_status
        not in {
            Task9ProviderReadinessStatus.READY,
            Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF,
        }
    ):
        raise ValueError(
            "TASK9_ANGEL_REQUEST_BUDGET_NOT_READY"
        )

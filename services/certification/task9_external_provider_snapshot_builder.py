"""Current Task 9 external-provider capability snapshot.

No external providers are selected. This builder performs no network work.
"""

from __future__ import annotations

from datetime import datetime

from services.contracts.task9_external_provider_state_v1 import (
    Task9ExternalCanonicalRole,
    Task9ExternalFailureSemantic,
    Task9ExternalProviderDomain,
    Task9ExternalProviderFreshness,
    Task9ExternalProviderSnapshotV1,
    Task9ExternalProviderStateV1,
    Task9ExternalProviderStatus,
)


_ROLES = {
    Task9ExternalProviderDomain.MARKET_BREADTH: (
        Task9ExternalCanonicalRole.OPTIONAL_CONFIRMATION
    ),
    Task9ExternalProviderDomain.FII_DII: (
        Task9ExternalCanonicalRole.OPTIONAL_CONFIRMATION
    ),
    Task9ExternalProviderDomain.ECONOMIC_EVENTS: (
        Task9ExternalCanonicalRole.OPTIONAL_ENTRY_RESTRICTION
    ),
    Task9ExternalProviderDomain.GLOBAL_MARKETS: (
        Task9ExternalCanonicalRole.OPTIONAL_CONTEXT
    ),
    Task9ExternalProviderDomain.STRUCTURED_NEWS: (
        Task9ExternalCanonicalRole.OPTIONAL_CONTEXT
    ),
}


def build_task9_external_provider_snapshot(
    *,
    snapshot_id: str,
    observed_at: datetime,
) -> Task9ExternalProviderSnapshotV1:
    """Build the provider-free current Task 9 external capability state."""

    if (
        not isinstance(observed_at, datetime)
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError("observed_at")

    states = tuple(
        Task9ExternalProviderStateV1(
            state_id=(
                f"{snapshot_id}:"
                f"{domain.value.lower()}"
            ),
            observed_at=observed_at,
            domain=domain,
            status=(
                Task9ExternalProviderStatus.PROVIDER_NOT_SELECTED
            ),
            availability=False,
            freshness=(
                Task9ExternalProviderFreshness.NOT_APPLICABLE
            ),
            canonical_role=_ROLES[domain],
            failure_semantic=(
                Task9ExternalFailureSemantic.OPTIONAL_UNAVAILABLE
            ),
            provider_name=None,
            provider_selected=False,
            network_calls_allowed=False,
            reason_code=(
                "TASK9_EXTERNAL_PROVIDER_NOT_SELECTED"
            ),
            provenance=(
                "task9-roadmap-provider-selection-state",
                "provider-free-current-build",
            ),
        )
        for domain in sorted(
            Task9ExternalProviderDomain,
            key=lambda item: item.value,
        )
    )

    return Task9ExternalProviderSnapshotV1(
        snapshot_id=snapshot_id,
        observed_at=observed_at,
        states=states,
    )


__all__ = (
    "build_task9_external_provider_snapshot",
)

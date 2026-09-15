"""Read Task 9 durable active-campaign projection into dashboard state.

No runtime, trading, provider, or campaign mutation occurs here.
"""
from __future__ import annotations

from collections.abc import MutableMapping

from services.dashboard_publication.task9_dashboard_active_campaign_projection_store import (
    Task9DashboardActiveCampaignProjectionStore,
)


TASK9_ACTIVE_CAMPAIGN_ID_STATE_KEY = (
    "task9_active_campaign_id"
)

TASK9_ACTIVE_OFFICIAL_RUN_ID_STATE_KEY = (
    "task9_active_official_run_id"
)

TASK9_ACTIVE_MARKET_DATE_STATE_KEY = (
    "task9_active_market_date"
)

TASK9_RUNTIME_CONFIG_SNAPSHOT_ID_STATE_KEY = (
    "task9_runtime_config_snapshot_id"
)

TASK9_RUNTIME_CONFIG_SHA256_STATE_KEY = (
    "task9_runtime_config_sha256"
)


def synchronize_task9_active_campaign_projection(
    state,
    *,
    persistence_root,
) -> bool:
    if not isinstance(
        state,
        MutableMapping,
    ):
        raise TypeError(
            "state must be mutable mapping"
        )

    projection = (
        Task9DashboardActiveCampaignProjectionStore(
            persistence_root
        ).get()
    )

    if projection is None:
        return False

    values = {
        TASK9_ACTIVE_CAMPAIGN_ID_STATE_KEY: (
            projection.campaign_id
        ),
        TASK9_ACTIVE_OFFICIAL_RUN_ID_STATE_KEY: (
            projection.active_official_run_id
        ),
        TASK9_ACTIVE_MARKET_DATE_STATE_KEY: (
            projection.active_market_date
        ),
        TASK9_RUNTIME_CONFIG_SNAPSHOT_ID_STATE_KEY: (
            projection.runtime_config_snapshot_id
        ),
        TASK9_RUNTIME_CONFIG_SHA256_STATE_KEY: (
            projection.runtime_config_sha256
        ),
    }

    changed = any(
        state.get(key) != value
        for key, value in values.items()
    )

    state.update(
        values
    )

    return changed


__all__ = (
    "TASK9_ACTIVE_CAMPAIGN_ID_STATE_KEY",
    "TASK9_ACTIVE_MARKET_DATE_STATE_KEY",
    "TASK9_ACTIVE_OFFICIAL_RUN_ID_STATE_KEY",
    "TASK9_RUNTIME_CONFIG_SHA256_STATE_KEY",
    "TASK9_RUNTIME_CONFIG_SNAPSHOT_ID_STATE_KEY",
    "synchronize_task9_active_campaign_projection",
)

"""Task 9 dashboard active-campaign authority projection."""
from __future__ import annotations

from datetime import datetime

from services.certification.task9_active_campaign_pointer_store import (
    Task9ActiveCampaignPointerStore,
)
from services.certification.task9_campaign_authority import (
    validate_task9_campaign_pointer_compatibility,
)
from services.certification.task9_campaign_manifest_store import (
    Task9CampaignManifestStore,
)
from services.contracts.task9_campaign_manifest_v1 import (
    Task9ActiveCampaignPointerStatus,
)
from services.contracts.task9_dashboard_active_campaign_projection_v1 import (
    Task9DashboardActiveCampaignProjectionV1,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseResultV1,
    Task9StartupPreflightPhaseStatus,
)
from services.dashboard_publication.task9_dashboard_active_campaign_projection_store import (
    Task9DashboardActiveCampaignProjectionStore,
)


def synchronize_task9_dashboard_active_campaign_projection(
    *,
    persistence_root,
    expected_campaign_id: str,
    expected_market_date,
    expected_official_run_id: str,
    expected_runtime_config_snapshot_id: str,
    expected_runtime_config_sha256: str,
    observed_at: datetime,
) -> Task9DashboardActiveCampaignProjectionV1:
    if (
        not isinstance(
            observed_at,
            datetime,
        )
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError(
            "observed_at"
        )

    pointer_store = (
        Task9ActiveCampaignPointerStore(
            persistence_root
        )
    )

    manifest_store = (
        Task9CampaignManifestStore(
            persistence_root
        )
    )

    pointer = pointer_store.get()

    if pointer is None:
        raise ValueError(
            "TASK9_ACTIVE_CAMPAIGN_POINTER_MISSING"
        )

    manifest = manifest_store.get(
        expected_campaign_id
    )

    if manifest is None:
        raise ValueError(
            "TASK9_CAMPAIGN_MANIFEST_MISSING"
        )

    # Campaign manifest provenance belongs to campaign creation.
    # After a canonical cross-day rollover, the active pointer belongs to
    # the current official run and therefore may carry a newer runtime
    # snapshot.  Keep campaign/root/status validation strict here; current
    # run provenance is verified independently against the expected
    # market-date/run/snapshot tuple below.
    validate_task9_campaign_pointer_compatibility(
        manifest,
        pointer,
        require_runtime_config_provenance_match=False,
    )

    if (
        pointer.status
        is not Task9ActiveCampaignPointerStatus.ACTIVE
    ):
        raise ValueError(
            "TASK9_ACTIVE_CAMPAIGN_NOT_ACTIVE"
        )

    expected = (
        expected_campaign_id,
        expected_market_date,
        expected_official_run_id,
        expected_runtime_config_snapshot_id,
        expected_runtime_config_sha256,
    )

    actual = (
        pointer.campaign_id,
        pointer.active_market_date,
        pointer.active_official_run_id,
        pointer.runtime_config_snapshot_id,
        pointer.runtime_config_sha256,
    )

    if actual != expected:
        raise ValueError(
            "TASK9_DASHBOARD_CAMPAIGN_AUTHORITY_MISMATCH"
        )

    projection = (
        Task9DashboardActiveCampaignProjectionV1(
            campaign_id=pointer.campaign_id,
            active_market_date=(
                pointer.active_market_date
            ),
            active_official_run_id=(
                pointer.active_official_run_id
            ),
            runtime_config_snapshot_id=(
                pointer.runtime_config_snapshot_id
            ),
            runtime_config_sha256=(
                pointer.runtime_config_sha256
            ),
            projected_at=observed_at,
        )
    )

    store = (
        Task9DashboardActiveCampaignProjectionStore(
            persistence_root
        )
    )

    saved = store.save(
        projection
    )

    durable = store.get()

    if durable is None:
        raise ValueError(
            "TASK9_DASHBOARD_CAMPAIGN_PROJECTION_NOT_DURABLE"
        )

    durable_identity = (
        durable.campaign_id,
        durable.active_market_date,
        durable.active_official_run_id,
        durable.runtime_config_snapshot_id,
        durable.runtime_config_sha256,
    )

    if durable_identity != expected:
        raise ValueError(
            "TASK9_DASHBOARD_CAMPAIGN_DURABLE_MISMATCH"
        )

    return saved


def build_task9_dashboard_active_campaign_preflight_phase(
    *,
    projection: Task9DashboardActiveCampaignProjectionV1,
    expected_campaign_id: str,
    expected_market_date,
    expected_official_run_id: str,
    expected_runtime_config_snapshot_id: str,
    expected_runtime_config_sha256: str,
    observed_at: datetime,
) -> Task9StartupPreflightPhaseResultV1:
    if (
        type(projection)
        is not Task9DashboardActiveCampaignProjectionV1
    ):
        raise TypeError(
            "projection"
        )

    expected = (
        expected_campaign_id,
        expected_market_date,
        expected_official_run_id,
        expected_runtime_config_snapshot_id,
        expected_runtime_config_sha256,
    )

    actual = (
        projection.campaign_id,
        projection.active_market_date,
        projection.active_official_run_id,
        projection.runtime_config_snapshot_id,
        projection.runtime_config_sha256,
    )

    ready = (
        actual == expected
    )

    return Task9StartupPreflightPhaseResultV1(
        phase=(
            Task9StartupPreflightPhase.DASHBOARD_ACTIVE_CAMPAIGN_AUTHORITY
        ),
        status=(
            Task9StartupPreflightPhaseStatus.PASS
            if ready
            else Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE
        ),
        blocking=not ready,
        reason_code=(
            "DASHBOARD_ACTIVE_CAMPAIGN_AUTHORITY_READY"
            if ready
            else "DASHBOARD_ACTIVE_CAMPAIGN_AUTHORITY_MISMATCH"
        ),
        detail=(
            None
            if ready
            else (
                "durable dashboard campaign projection "
                "does not match startup campaign authority"
            )
        ),
        observed_at=observed_at,
    )


__all__ = (
    "build_task9_dashboard_active_campaign_preflight_phase",
    "synchronize_task9_dashboard_active_campaign_projection",
)

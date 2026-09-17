"""Initialize the first durable Task 9 certification campaign.

This authority exists only for the zero-campaign state.  Normal campaign-day
and run transitions remain owned by task9_campaign_rollover.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

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
    Task9ActiveCampaignPointerV1,
    Task9CampaignManifestV1,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    Task9RuntimeConfigSnapshotV1,
)
from services.contracts.task9_runtime_config_v1 import (
    Task9RuntimeConfigV1,
)


def _policy_references(
    runtime_config: Task9RuntimeConfigV1,
) -> Mapping[str, str]:
    value = getattr(
        runtime_config,
        "canonical_policy_references",
        None,
    )

    if value is None:
        value = getattr(
            runtime_config,
            "policy_references",
            None,
        )

    if not isinstance(value, Mapping):
        raise ValueError(
            "TASK9_CAMPAIGN_POLICY_REFERENCES_MISSING"
        )

    return dict(value)


def initialize_task9_first_campaign(
    *,
    runtime_config: Task9RuntimeConfigV1,
    snapshot: Task9RuntimeConfigSnapshotV1,
    observed_at: datetime,
) -> tuple[
    Task9CampaignManifestV1,
    Task9ActiveCampaignPointerV1,
]:
    if type(runtime_config) is not Task9RuntimeConfigV1:
        raise TypeError("runtime_config")

    if type(snapshot) is not Task9RuntimeConfigSnapshotV1:
        raise TypeError("snapshot")

    if (
        not isinstance(observed_at, datetime)
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError("observed_at")

    if (
        runtime_config.execution_mode != "PAPER"
        or runtime_config.broker_order_submission is not False
        or runtime_config.live_execution_eligible is not False
        or runtime_config.run_classification
        != "OFFICIAL_CERTIFICATION"
    ):
        raise ValueError(
            "TASK9_FIRST_CAMPAIGN_REQUIRES_SAFE_OFFICIAL_PAPER"
        )

    persistence_root = Path(
        runtime_config.authoritative_persistence_root
    )

    registry_location = Path(
        runtime_config.campaign_registry_location
    )

    registry_root = registry_location.parent

    campaign_root = (
        persistence_root
        / "campaigns"
        / runtime_config.campaign_id
    )

    manifest_ref = (
        persistence_root
        / "campaigns"
        / f"{runtime_config.campaign_id}.json"
    )

    manifest_store = Task9CampaignManifestStore(
        persistence_root
    )

    pointer_store = Task9ActiveCampaignPointerStore(
        persistence_root
    )

    existing_manifest = manifest_store.get(
        runtime_config.campaign_id
    )

    existing_pointer = pointer_store.get()

    # First-campaign initialization is legal only when both authorities
    # are absent.  Partial state is treated as corruption/recovery work,
    # never silently repaired.
    if (
        existing_manifest is None
        and existing_pointer is not None
    ):
        raise ValueError(
            "TASK9_FIRST_CAMPAIGN_ORPHAN_POINTER"
        )

    if (
        existing_manifest is not None
        and existing_pointer is None
    ):
        raise ValueError(
            "TASK9_FIRST_CAMPAIGN_ORPHAN_MANIFEST"
        )

    if (
        existing_manifest is not None
        and existing_pointer is not None
    ):
        validate_task9_campaign_pointer_compatibility(
            existing_manifest,
            existing_pointer,
        )

        expected = (
            runtime_config.campaign_id,
            runtime_config.market_date,
            runtime_config.official_run_id,
            snapshot.snapshot_id,
            snapshot.content_sha256,
        )

        actual = (
            existing_pointer.campaign_id,
            existing_pointer.active_market_date,
            existing_pointer.active_official_run_id,
            existing_pointer.runtime_config_snapshot_id,
            existing_pointer.runtime_config_sha256,
        )

        if actual != expected:
            raise ValueError(
                "TASK9_FIRST_CAMPAIGN_EXISTING_AUTHORITY_CONFLICT"
            )

        return (
            existing_manifest,
            existing_pointer,
        )

    manifest = Task9CampaignManifestV1(
        campaign_id=runtime_config.campaign_id,
        campaign_version="1",
        campaign_status="ACTIVE",
        created_market_date=runtime_config.market_date,
        registry_root=registry_root.as_posix(),
        campaign_root=campaign_root.as_posix(),
        runtime_config_snapshot_id=snapshot.snapshot_id,
        runtime_config_sha256=snapshot.content_sha256,
        canonical_policy_references=(
            _policy_references(runtime_config)
        ),
    )

    pointer = Task9ActiveCampaignPointerV1(
        campaign_id=runtime_config.campaign_id,
        campaign_manifest_ref=manifest_ref.as_posix(),
        campaign_root=campaign_root.as_posix(),
        registry_root=registry_root.as_posix(),
        active_market_date=runtime_config.market_date,
        active_official_run_id=(
            runtime_config.official_run_id
        ),
        run_classification="OFFICIAL_CERTIFICATION",
        runtime_config_snapshot_id=snapshot.snapshot_id,
        runtime_config_sha256=snapshot.content_sha256,
        updated_at=observed_at,
        status="ACTIVE",
    )

    # Manifest-before-pointer is deliberate.  A crash between these writes
    # leaves visible orphan state and must fail closed on restart.
    saved_manifest = manifest_store.save(
        manifest
    )

    saved_pointer = pointer_store.set(
        pointer,
        manifest=saved_manifest,
    )

    validate_task9_campaign_pointer_compatibility(
        saved_manifest,
        saved_pointer,
    )

    return (
        saved_manifest,
        saved_pointer,
    )


__all__ = (
    "initialize_task9_first_campaign",
)

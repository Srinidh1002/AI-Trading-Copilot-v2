from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.certification.task9_active_campaign_pointer_store import (
    Task9ActiveCampaignPointerStore,
)
from services.certification.task9_campaign_manifest_store import (
    Task9CampaignManifestStore,
)
from services.certification.task9_first_campaign_initializer import (
    initialize_task9_first_campaign,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    build_task9_runtime_config_snapshot,
)
from services.contracts.task9_campaign_manifest_v1 import (
    Task9ActiveCampaignPointerV1,
    Task9CampaignManifestV1,
)
from tests.test_task9_runtime_config_snapshot_v1 import (
    _config,
)


NOW = datetime(
    2026,
    8,
    18,
    4,
    40,
    tzinfo=timezone.utc,
)


def _runtime(tmp_path):
    return replace(
        _config(),
        campaign_id="task9104-campaign",
        official_run_id="task9104-run",
        market_date=NOW.date(),
        authoritative_persistence_root=str(
            tmp_path / "task9"
        ),
        campaign_registry_location=str(
            tmp_path
            / "task9"
            / "campaign-registry.json"
        ),
    )


def _initialize(tmp_path):
    runtime = _runtime(tmp_path)
    snapshot = (
        build_task9_runtime_config_snapshot(
            runtime
        )
    )

    manifest, pointer = (
        initialize_task9_first_campaign(
            runtime_config=runtime,
            snapshot=snapshot,
            observed_at=NOW,
        )
    )

    return (
        runtime,
        snapshot,
        manifest,
        pointer,
    )


def test_first_campaign_creates_manifest_then_compatible_pointer(
    tmp_path,
):
    runtime, snapshot, manifest, pointer = (
        _initialize(tmp_path)
    )

    root = Path(
        runtime.authoritative_persistence_root
    )

    persisted_manifest = (
        Task9CampaignManifestStore(
            root
        ).get(
            runtime.campaign_id
        )
    )

    persisted_pointer = (
        Task9ActiveCampaignPointerStore(
            root
        ).get()
    )

    assert persisted_manifest == manifest
    assert persisted_pointer == pointer

    assert manifest.campaign_id == runtime.campaign_id
    assert manifest.campaign_status.value == "ACTIVE"

    assert manifest.target_nifty_count == 100
    assert manifest.target_sensex_count == 100

    assert (
        manifest.replay_counts_toward_target
        is False
    )
    assert (
        manifest.diagnostic_counts_toward_target
        is False
    )
    assert (
        manifest.wait_counts_toward_target
        is False
    )
    assert (
        manifest.no_trade_counts_toward_target
        is False
    )

    assert manifest.execution_mode == "PAPER"
    assert manifest.broker_order_submission is False
    assert manifest.live_execution_eligible is False

    assert (
        pointer.active_official_run_id
        == runtime.official_run_id
    )
    assert (
        pointer.active_market_date
        == runtime.market_date
    )
    assert pointer.status.value == "ACTIVE"

    assert (
        pointer.runtime_config_snapshot_id
        == snapshot.snapshot_id
    )
    assert (
        pointer.runtime_config_sha256
        == snapshot.content_sha256
    )


def test_first_campaign_exact_restart_is_idempotent(
    tmp_path,
):
    first = _initialize(
        tmp_path
    )

    second = _initialize(
        tmp_path
    )

    assert first[2] == second[2]
    assert first[3] == second[3]


def test_first_campaign_rejects_orphan_manifest(
    tmp_path,
):
    runtime = _runtime(
        tmp_path
    )

    snapshot = (
        build_task9_runtime_config_snapshot(
            runtime
        )
    )

    manifest = Task9CampaignManifestV1(
        campaign_id=runtime.campaign_id,
        campaign_version="1",
        campaign_status="ACTIVE",
        created_market_date=(
            runtime.market_date
        ),
        registry_root=(
            Path(
                runtime.campaign_registry_location
            ).parent.as_posix()
        ),
        campaign_root=(
            (
                Path(runtime.authoritative_persistence_root)
                / "campaigns"
                / runtime.campaign_id
            ).as_posix()
        ),
        runtime_config_snapshot_id=(
            snapshot.snapshot_id
        ),
        runtime_config_sha256=(
            snapshot.content_sha256
        ),
        canonical_policy_references=(
            runtime.policy_references
        ),
    )

    Task9CampaignManifestStore(
        runtime.authoritative_persistence_root
    ).save(
        manifest
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_FIRST_CAMPAIGN_ORPHAN_MANIFEST"
        ),
    ):
        initialize_task9_first_campaign(
            runtime_config=runtime,
            snapshot=snapshot,
            observed_at=NOW,
        )


def test_first_campaign_rejects_orphan_pointer(
    tmp_path,
):
    runtime = _runtime(
        tmp_path
    )

    snapshot = (
        build_task9_runtime_config_snapshot(
            runtime
        )
    )

    root = Path(
        runtime.authoritative_persistence_root
    )

    pointer = Task9ActiveCampaignPointerV1(
        campaign_id=runtime.campaign_id,
        campaign_manifest_ref=(
            root
            / "campaigns"
            / f"{runtime.campaign_id}.json"
        ).as_posix(),
        campaign_root=(
            root
            / "campaigns"
            / runtime.campaign_id
        ).as_posix(),
        registry_root=(
            Path(
                runtime.campaign_registry_location
            ).parent.as_posix()
        ),
        active_market_date=runtime.market_date,
        active_official_run_id=(
            runtime.official_run_id
        ),
        run_classification=(
            "OFFICIAL_CERTIFICATION"
        ),
        runtime_config_snapshot_id=(
            snapshot.snapshot_id
        ),
        runtime_config_sha256=(
            snapshot.content_sha256
        ),
        updated_at=NOW,
        status="ACTIVE",
    )

    Task9ActiveCampaignPointerStore(
        root
    ).set(
        pointer
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_FIRST_CAMPAIGN_ORPHAN_POINTER"
        ),
    ):
        initialize_task9_first_campaign(
            runtime_config=runtime,
            snapshot=snapshot,
            observed_at=NOW,
        )


def test_first_campaign_rejects_existing_identity_conflict(
    tmp_path,
):
    runtime, snapshot, manifest, pointer = (
        _initialize(tmp_path)
    )

    conflicting_pointer = replace(
        pointer,
        active_official_run_id=(
            "task9104-other-run"
        ),
        updated_at=NOW,
    )

    Task9ActiveCampaignPointerStore(
        runtime.authoritative_persistence_root
    ).set(
        conflicting_pointer,
        manifest=manifest,
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_FIRST_CAMPAIGN_"
            "EXISTING_AUTHORITY_CONFLICT"
        ),
    ):
        initialize_task9_first_campaign(
            runtime_config=runtime,
            snapshot=snapshot,
            observed_at=NOW,
        )

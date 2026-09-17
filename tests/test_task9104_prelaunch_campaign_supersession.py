from dataclasses import replace
from datetime import datetime, timezone
import json
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
from services.certification.task9_prelaunch_campaign_supersession import (
    prepare_task9_startup_campaign_authority,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    build_task9_runtime_config_snapshot,
)
from tests.test_task9_runtime_config_snapshot_v1 import (
    _config,
)


NOW = datetime(
    2026,
    8,
    18,
    5,
    45,
    tzinfo=timezone.utc,
)


def _runtime(
    tmp_path,
    *,
    campaign_id="task9104-old-campaign",
    run_id="task9104-old-run",
):
    return replace(
        _config(),
        campaign_id=campaign_id,
        official_run_id=run_id,
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


def _old_authority(tmp_path):
    runtime = _runtime(
        tmp_path
    )

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


def _new_runtime(
    old_runtime,
):
    return replace(
        old_runtime,
        campaign_id=(
            "task9104-new-campaign"
        ),
        official_run_id=(
            "task9104-new-run"
        ),
        option_quote_max_age_seconds=300.0,
    )


def test_supersedes_unused_prelaunch_campaign(
    tmp_path,
):
    (
        old_runtime,
        old_snapshot,
        old_manifest,
        old_pointer,
    ) = _old_authority(
        tmp_path
    )

    new_runtime = _new_runtime(
        old_runtime
    )

    new_snapshot = (
        build_task9_runtime_config_snapshot(
            new_runtime
        )
    )

    assert (
        new_snapshot.snapshot_id
        != old_snapshot.snapshot_id
    )

    manifest, pointer = (
        prepare_task9_startup_campaign_authority(
            runtime_config=new_runtime,
            snapshot=new_snapshot,
            observed_at=NOW,
        )
    )

    root = Path(
        new_runtime.authoritative_persistence_root
    )

    assert (
        manifest.campaign_id
        == new_runtime.campaign_id
    )

    assert (
        pointer.campaign_id
        == new_runtime.campaign_id
    )

    assert (
        pointer.active_official_run_id
        == new_runtime.official_run_id
    )

    assert (
        pointer.runtime_config_snapshot_id
        == new_snapshot.snapshot_id
    )

    assert (
        pointer.runtime_config_sha256
        == new_snapshot.content_sha256
    )

    # Historical first campaign is preserved unchanged.
    assert (
        Task9CampaignManifestStore(
            root
        ).get(
            old_runtime.campaign_id
        )
        == old_manifest
    )

    durable = (
        Task9ActiveCampaignPointerStore(
            root
        ).get()
    )

    assert durable == pointer

    receipts = list(
        (
            root
            / "campaign-supersessions"
        ).glob(
            "*.json"
        )
    )

    assert len(receipts) == 1

    receipt = json.loads(
        receipts[0].read_text(
            encoding="utf-8"
        )
    )

    assert (
        receipt["status"]
        == "APPLIED"
    )

    assert (
        receipt["old_campaign_id"]
        == old_runtime.campaign_id
    )

    assert (
        receipt["new_campaign_id"]
        == new_runtime.campaign_id
    )

    assert (
        receipt[
            "old_runtime_config_sha256"
        ]
        == old_pointer.runtime_config_sha256
    )

    assert (
        receipt[
            "new_runtime_config_sha256"
        ]
        == new_snapshot.content_sha256
    )

    assert (
        receipt[
            "broker_order_submission"
        ]
        is False
    )

    assert (
        receipt[
            "live_execution_eligible"
        ]
        is False
    )


def test_exact_restart_after_supersession_is_idempotent(
    tmp_path,
):
    old_runtime, *_ = (
        _old_authority(
            tmp_path
        )
    )

    new_runtime = _new_runtime(
        old_runtime
    )

    new_snapshot = (
        build_task9_runtime_config_snapshot(
            new_runtime
        )
    )

    first = (
        prepare_task9_startup_campaign_authority(
            runtime_config=new_runtime,
            snapshot=new_snapshot,
            observed_at=NOW,
        )
    )

    second = (
        prepare_task9_startup_campaign_authority(
            runtime_config=new_runtime,
            snapshot=new_snapshot,
            observed_at=NOW,
        )
    )

    assert first == second


def test_same_campaign_snapshot_conflict_still_fails_closed(
    tmp_path,
):
    old_runtime, *_ = (
        _old_authority(
            tmp_path
        )
    )

    changed = replace(
        old_runtime,
        option_quote_max_age_seconds=301.0,
    )

    changed_snapshot = (
        build_task9_runtime_config_snapshot(
            changed
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_FIRST_CAMPAIGN_"
            "EXISTING_AUTHORITY_CONFLICT"
        ),
    ):
        prepare_task9_startup_campaign_authority(
            runtime_config=changed,
            snapshot=changed_snapshot,
            observed_at=NOW,
        )


def test_rejects_approved_old_preflight(
    tmp_path,
):
    old_runtime, *_ = (
        _old_authority(
            tmp_path
        )
    )

    root = Path(
        old_runtime.authoritative_persistence_root
    )

    preflight_root = (
        root
        / "startup-preflights"
    )

    preflight_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        preflight_root
        / "approved.json"
    ).write_text(
        json.dumps(
            {
                "official_run_id": (
                    old_runtime.official_run_id
                ),
                "launch_approved": True,
            }
        ),
        encoding="utf-8",
    )

    new_runtime = _new_runtime(
        old_runtime
    )

    new_snapshot = (
        build_task9_runtime_config_snapshot(
            new_runtime
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_PRELAUNCH_SUPERSESSION_"
            "APPROVED_PREFLIGHT_EXISTS"
        ),
    ):
        prepare_task9_startup_campaign_authority(
            runtime_config=new_runtime,
            snapshot=new_snapshot,
            observed_at=NOW,
        )


def test_rejects_unknown_old_run_activity(
    tmp_path,
):
    old_runtime, *_ = (
        _old_authority(
            tmp_path
        )
    )

    root = Path(
        old_runtime.authoritative_persistence_root
    )

    activity = (
        root
        / "lifecycle"
        / "unexpected.json"
    )

    activity.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    activity.write_text(
        json.dumps(
            {
                "official_run_id": (
                    old_runtime.official_run_id
                )
            }
        ),
        encoding="utf-8",
    )

    new_runtime = _new_runtime(
        old_runtime
    )

    new_snapshot = (
        build_task9_runtime_config_snapshot(
            new_runtime
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_PRELAUNCH_SUPERSESSION_"
            "OLD_RUN_ACTIVITY_EXISTS"
        ),
    ):
        prepare_task9_startup_campaign_authority(
            runtime_config=new_runtime,
            snapshot=new_snapshot,
            observed_at=NOW,
        )


def test_requires_different_campaign_and_run_identity(
    tmp_path,
):
    old_runtime, *_ = (
        _old_authority(
            tmp_path
        )
    )

    same_run = replace(
        old_runtime,
        campaign_id=(
            "task9104-new-campaign"
        ),
        option_quote_max_age_seconds=300.0,
    )

    same_run_snapshot = (
        build_task9_runtime_config_snapshot(
            same_run
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_PRELAUNCH_SUPERSESSION_"
            "NEW_RUN_REQUIRED"
        ),
    ):
        prepare_task9_startup_campaign_authority(
            runtime_config=same_run,
            snapshot=same_run_snapshot,
            observed_at=NOW,
        )


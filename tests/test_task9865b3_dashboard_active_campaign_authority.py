from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from dashboard.task9_active_campaign_sync import (
    TASK9_ACTIVE_CAMPAIGN_ID_STATE_KEY,
    TASK9_ACTIVE_OFFICIAL_RUN_ID_STATE_KEY,
    synchronize_task9_active_campaign_projection,
)
from services.certification.task9_active_campaign_pointer_store import (
    Task9ActiveCampaignPointerStore,
)
from services.certification.task9_campaign_manifest_store import (
    Task9CampaignManifestStore,
)
from services.certification.task9_dashboard_active_campaign_authority import (
    build_task9_dashboard_active_campaign_preflight_phase,
    synchronize_task9_dashboard_active_campaign_projection,
)
from services.contracts.task9_campaign_manifest_v1 import (
    Task9ActiveCampaignPointerStatus,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseStatus,
)


NOW = datetime(
    2026,
    8,
    17,
    13,
    30,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)

DAY = date(
    2026,
    8,
    17,
)


def _seed_campaign(tmp_path):
    from tests.test_task9_active_campaign_pointer_store import (
        _manifest,
        _pointer,
    )

    m = _manifest()

    p = _pointer()

    p = replace(
        p,
        status=(
            Task9ActiveCampaignPointerStatus.ACTIVE
        ),
    )

    Task9CampaignManifestStore(
        tmp_path
    ).save(
        m
    )

    Task9ActiveCampaignPointerStore(
        tmp_path
    ).set(
        p,
        manifest=m,
    )

    return m, p


def _sync(tmp_path, p):
    return (
        synchronize_task9_dashboard_active_campaign_projection(
            persistence_root=tmp_path,
            expected_campaign_id=p.campaign_id,
            expected_market_date=p.active_market_date,
            expected_official_run_id=(
                p.active_official_run_id
            ),
            expected_runtime_config_snapshot_id=(
                p.runtime_config_snapshot_id
            ),
            expected_runtime_config_sha256=(
                p.runtime_config_sha256
            ),
            observed_at=NOW,
        )
    )


def test_projection_comes_from_canonical_pointer_and_manifest(
    tmp_path,
):
    _, pointer = _seed_campaign(
        tmp_path
    )

    projection = _sync(
        tmp_path,
        pointer,
    )

    assert (
        projection.campaign_id
        == pointer.campaign_id
    )

    assert (
        projection.active_official_run_id
        == pointer.active_official_run_id
    )

    assert (
        projection.runtime_config_sha256
        == pointer.runtime_config_sha256
    )


def test_projection_missing_pointer_fails_closed(
    tmp_path,
):
    from tests.test_task9_active_campaign_pointer_store import (
        _manifest,
    )

    m = _manifest()

    Task9CampaignManifestStore(
        tmp_path
    ).save(
        m
    )

    with pytest.raises(
        ValueError,
        match="POINTER_MISSING",
    ):
        synchronize_task9_dashboard_active_campaign_projection(
            persistence_root=tmp_path,
            expected_campaign_id=m.campaign_id,
            expected_market_date=DAY,
            expected_official_run_id="run-1",
            expected_runtime_config_snapshot_id="snapshot-1",
            expected_runtime_config_sha256="a" * 64,
            observed_at=NOW,
        )


def test_stale_expected_run_fails_closed(
    tmp_path,
):
    _, pointer = _seed_campaign(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="AUTHORITY_MISMATCH",
    ):
        synchronize_task9_dashboard_active_campaign_projection(
            persistence_root=tmp_path,
            expected_campaign_id=pointer.campaign_id,
            expected_market_date=pointer.active_market_date,
            expected_official_run_id="stale-run",
            expected_runtime_config_snapshot_id=(
                pointer.runtime_config_snapshot_id
            ),
            expected_runtime_config_sha256=(
                pointer.runtime_config_sha256
            ),
            observed_at=NOW,
        )


def test_projection_builds_pass_preflight_phase(
    tmp_path,
):
    _, pointer = _seed_campaign(
        tmp_path
    )

    projection = _sync(
        tmp_path,
        pointer,
    )

    phase = (
        build_task9_dashboard_active_campaign_preflight_phase(
            projection=projection,
            expected_campaign_id=pointer.campaign_id,
            expected_market_date=pointer.active_market_date,
            expected_official_run_id=(
                pointer.active_official_run_id
            ),
            expected_runtime_config_snapshot_id=(
                pointer.runtime_config_snapshot_id
            ),
            expected_runtime_config_sha256=(
                pointer.runtime_config_sha256
            ),
            observed_at=NOW,
        )
    )

    assert (
        phase.phase
        is Task9StartupPreflightPhase.DASHBOARD_ACTIVE_CAMPAIGN_AUTHORITY
    )

    assert (
        phase.status
        is Task9StartupPreflightPhaseStatus.PASS
    )

    assert phase.blocking is False


def test_dashboard_reads_durable_projection_without_mutating_campaign(
    tmp_path,
):
    _, pointer = _seed_campaign(
        tmp_path
    )

    _sync(
        tmp_path,
        pointer,
    )

    before = (
        Task9ActiveCampaignPointerStore(
            tmp_path
        ).get()
    )

    state = {}

    changed = (
        synchronize_task9_active_campaign_projection(
            state,
            persistence_root=tmp_path,
        )
    )

    after = (
        Task9ActiveCampaignPointerStore(
            tmp_path
        ).get()
    )

    assert changed is True

    assert (
        state[
            TASK9_ACTIVE_CAMPAIGN_ID_STATE_KEY
        ]
        == pointer.campaign_id
    )

    assert (
        state[
            TASK9_ACTIVE_OFFICIAL_RUN_ID_STATE_KEY
        ]
        == pointer.active_official_run_id
    )

    assert before == after


def test_dashboard_missing_projection_does_not_fabricate_identity(
    tmp_path,
):
    state = {}

    changed = (
        synchronize_task9_active_campaign_projection(
            state,
            persistence_root=tmp_path,
        )
    )

    assert changed is False

    assert (
        TASK9_ACTIVE_CAMPAIGN_ID_STATE_KEY
        not in state
    )


def test_projection_remains_paper_only(
    tmp_path,
):
    _, pointer = _seed_campaign(
        tmp_path
    )

    projection = _sync(
        tmp_path,
        pointer,
    )

    assert (
        projection.execution_mode
        == "PAPER"
    )

    assert (
        projection.broker_order_submission
        is False
    )

    assert (
        projection.live_execution_eligible
        is False
    )

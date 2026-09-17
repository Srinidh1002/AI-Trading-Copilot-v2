from datetime import date, datetime, timezone

from services.certification.task9_active_campaign_pointer_store import (
    Task9ActiveCampaignPointerStore,
)
from services.certification.task9_campaign_manifest_store import (
    Task9CampaignManifestStore,
)
from services.certification.task9_live_paper_certification_launcher import (
    Task9LivePaperRunManifestV1,
)
from services.certification.task9_official_run_manifest_store import (
    Task9OfficialRunManifestStore,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    build_task9_runtime_config_snapshot,
)
from services.certification.task9_startup_campaign_transition import (
    prepare_task9_startup_campaign_authority,
)
from services.contracts.task9_campaign_manifest_v1 import (
    Task9ActiveCampaignPointerStatus,
    Task9ActiveCampaignPointerV1,
    Task9CampaignManifestV1,
    Task9CampaignStatus,
)
from services.contracts.task9_runtime_config_v1 import (
    Task9RuntimeConfigV1,
)


NOW = datetime(
    2026,
    8,
    19,
    6,
    0,
    tzinfo=timezone.utc,
)

CAMPAIGN_ID = (
    "task9-live-certification-2026-08-18-r2"
)

RUN_ID = "task9-live-20260819-r2"

CREATION_SHA = "a" * 64
CREATION_SID = (
    "task9-runtime-config-" + CREATION_SHA
)

POLICIES = {
    "canonical_directional": "directional.v1",
    "contract_selection": "contract-selection.v1",
    "contract_spread": "spread.v1",
    "counting": "counting.v1",
    "failure_disposition": "failure-disposition.v1",
    "lifecycle": "lifecycle.v1",
    "liquidity": "liquidity.v1",
    "minimum_risk_reward": "rr.v1",
    "portfolio_concurrency": "portfolio.v1",
    "risk": "risk.v1",
    "session": "session.v1",
    "stop_target": "stop-target.v1",
}


def _runtime_config(
    tmp_path,
):
    return Task9RuntimeConfigV1(
        runtime_config_id=(
            "task9-runtime-2026-08-19-r2"
        ),
        runtime_config_version="1",
        market_date=date(
            2026,
            8,
            19,
        ),
        campaign_registry_location=str(
            tmp_path / "campaign-registry.json"
        ),
        campaign_id=CAMPAIGN_ID,
        official_run_id=RUN_ID,
        official_root=str(
            tmp_path / "official"
        ),
        certification_registry_root=str(
            tmp_path / "certification-registry"
        ),
        authoritative_persistence_root=str(
            tmp_path
        ),
        dashboard_publication_location=str(
            tmp_path / "dashboard-publication.json"
        ),
        available_capital=10000.0,
        trade_risk_fraction=0.02,
        maximum_daily_loss_fraction=0.02,
        maximum_lots=10,
        maximum_quantity=100,
        maximum_spread_fraction=0.25,
        parent_cycle_cadence_seconds=1.0,
        collector_heartbeat_seconds=1.0,
        market_quote_max_age_seconds=5.0,
        option_quote_max_age_seconds=300.0,
        instrument_master_max_age_seconds=(
            24.0 * 60.0 * 60.0
        ),
        policy_references=POLICIES,
        run_classification=(
            "OFFICIAL_CERTIFICATION"
        ),
        emergency_halt_enabled=False,
        emergency_halt_reason=None,
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


def _campaign_manifest(
    tmp_path,
):
    return Task9CampaignManifestV1(
        campaign_id=CAMPAIGN_ID,
        campaign_version="1",
        campaign_status=(
            Task9CampaignStatus.ACTIVE
        ),
        created_market_date=date(
            2026,
            8,
            18,
        ),
        registry_root=str(tmp_path),
        campaign_root=str(
            tmp_path
            / "campaigns"
            / CAMPAIGN_ID
        ),
        runtime_config_snapshot_id=(
            CREATION_SID
        ),
        runtime_config_sha256=(
            CREATION_SHA
        ),
        canonical_policy_references=(
            POLICIES
        ),
    )


def _active_pointer(
    tmp_path,
    snapshot,
):
    return Task9ActiveCampaignPointerV1(
        campaign_id=CAMPAIGN_ID,
        campaign_manifest_ref=str(
            tmp_path
            / "campaigns"
            / f"{CAMPAIGN_ID}.json"
        ),
        campaign_root=str(
            tmp_path
            / "campaigns"
            / CAMPAIGN_ID
        ),
        registry_root=str(tmp_path),
        active_market_date=date(
            2026,
            8,
            19,
        ),
        active_official_run_id=RUN_ID,
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
        status=(
            Task9ActiveCampaignPointerStatus.ACTIVE
        ),
        startup_preflight_id=None,
    )


def _official_run_manifest(
    snapshot,
):
    return Task9LivePaperRunManifestV1(
        official_run_id=RUN_ID,
        official_start_at=NOW,
        run_classification=(
            "OFFICIAL_CERTIFICATION"
        ),
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
        runtime_config_snapshot_id=(
            snapshot.snapshot_id
        ),
        runtime_config_sha256=(
            snapshot.content_sha256
        ),
        campaign_id=CAMPAIGN_ID,
        market_date=date(
            2026,
            8,
            19,
        ),
    )


def test_same_day_restart_after_cross_day_rollover_accepts_active_run_provenance(
    tmp_path,
):
    runtime_config = _runtime_config(
        tmp_path
    )

    snapshot = (
        build_task9_runtime_config_snapshot(
            runtime_config
        )
    )

    manifest = _campaign_manifest(
        tmp_path
    )

    pointer = _active_pointer(
        tmp_path,
        snapshot,
    )

    run_manifest = (
        _official_run_manifest(
            snapshot
        )
    )

    # Prove this is genuinely a cross-day provenance split.
    assert (
        manifest.runtime_config_snapshot_id
        != pointer.runtime_config_snapshot_id
    )

    assert (
        manifest.runtime_config_sha256
        != pointer.runtime_config_sha256
    )

    manifest_store = (
        Task9CampaignManifestStore(
            tmp_path
        )
    )

    pointer_store = (
        Task9ActiveCampaignPointerStore(
            tmp_path
        )
    )

    run_store = (
        Task9OfficialRunManifestStore(
            tmp_path
        )
    )

    manifest_store.save(
        manifest
    )

    pointer_store.set(
        pointer,
        manifest=manifest,
        require_runtime_config_provenance_match=False,
    )

    run_store.save(
        run_manifest
    )

    before_pointer = (
        pointer_store.get()
    )

    result_manifest, result_pointer, receipt = (
        prepare_task9_startup_campaign_authority(
            runtime_config=runtime_config,
            snapshot=snapshot,
            observed_at=NOW,
        )
    )

    after_pointer = (
        pointer_store.get()
    )

    assert result_manifest == manifest
    assert result_pointer == pointer

    assert before_pointer == pointer
    assert after_pointer == pointer

    assert receipt is None

    assert (
        result_pointer.runtime_config_snapshot_id
        == snapshot.snapshot_id
    )

    assert (
        result_pointer.runtime_config_sha256
        == snapshot.content_sha256
    )

    assert (
        result_manifest.runtime_config_snapshot_id
        == CREATION_SID
    )

    assert (
        result_manifest.runtime_config_sha256
        == CREATION_SHA
    )

    assert (
        run_store.get(RUN_ID)
        == run_manifest
    )

def test_dashboard_projection_accepts_cross_day_active_run_provenance(
    tmp_path,
):
    from services.certification.task9_dashboard_active_campaign_authority import (
        synchronize_task9_dashboard_active_campaign_projection,
    )

    runtime_config = _runtime_config(
        tmp_path
    )

    snapshot = (
        build_task9_runtime_config_snapshot(
            runtime_config
        )
    )

    manifest = _campaign_manifest(
        tmp_path
    )

    pointer = _active_pointer(
        tmp_path,
        snapshot,
    )

    Task9CampaignManifestStore(
        tmp_path
    ).save(
        manifest
    )

    Task9ActiveCampaignPointerStore(
        tmp_path
    ).set(
        pointer,
        manifest=manifest,
        require_runtime_config_provenance_match=False,
    )

    projection = (
        synchronize_task9_dashboard_active_campaign_projection(
            persistence_root=tmp_path,
            expected_campaign_id=(
                runtime_config.campaign_id
            ),
            expected_market_date=(
                runtime_config.market_date
            ),
            expected_official_run_id=(
                runtime_config.official_run_id
            ),
            expected_runtime_config_snapshot_id=(
                snapshot.snapshot_id
            ),
            expected_runtime_config_sha256=(
                snapshot.content_sha256
            ),
            observed_at=NOW,
        )
    )

    assert (
        projection.campaign_id
        == runtime_config.campaign_id
    )

    assert (
        projection.active_market_date
        == runtime_config.market_date
    )

    assert (
        projection.active_official_run_id
        == runtime_config.official_run_id
    )

    assert (
        projection.runtime_config_snapshot_id
        == snapshot.snapshot_id
    )

    assert (
        projection.runtime_config_sha256
        == snapshot.content_sha256
    )

    # Campaign creation provenance remains untouched.
    persisted_manifest = (
        Task9CampaignManifestStore(
            tmp_path
        ).get(
            runtime_config.campaign_id
        )
    )

    assert (
        persisted_manifest.runtime_config_snapshot_id
        == CREATION_SID
    )

    assert (
        persisted_manifest.runtime_config_sha256
        == CREATION_SHA
    )

def test_campaign_preflight_accepts_cross_day_active_run_provenance(
    tmp_path,
):
    from services.certification.task9_campaign_preflight_bridge import (
        build_task9_campaign_preflight_phase,
    )

    runtime_config = _runtime_config(
        tmp_path
    )

    snapshot = (
        build_task9_runtime_config_snapshot(
            runtime_config
        )
    )

    manifest = _campaign_manifest(
        tmp_path
    )

    pointer = _active_pointer(
        tmp_path,
        snapshot,
    )

    manifest_store = (
        Task9CampaignManifestStore(
            tmp_path
        )
    )

    pointer_store = (
        Task9ActiveCampaignPointerStore(
            tmp_path
        )
    )

    manifest_store.save(
        manifest
    )

    pointer_store.set(
        pointer,
        manifest=manifest,
        require_runtime_config_provenance_match=False,
    )

    result = (
        build_task9_campaign_preflight_phase(
            runtime_config=runtime_config,
            manifest_store=manifest_store,
            pointer_store=pointer_store,
            observed_at=NOW,
            runtime_config_snapshot_id=(
                snapshot.snapshot_id
            ),
            runtime_config_sha256=(
                snapshot.content_sha256
            ),
            campaign_index=None,
        )
    )

    assert result.status.value == "PASS"
    assert result.blocking is False

    assert (
        result.reason_code
        == "CAMPAIGN_AUTHORITY_VALID"
    )

    # Campaign creation provenance remains immutable.
    assert (
        manifest.runtime_config_snapshot_id
        == CREATION_SID
    )

    assert (
        manifest.runtime_config_sha256
        == CREATION_SHA
    )

    # Active pointer still carries the current run provenance.
    assert (
        pointer.runtime_config_snapshot_id
        == snapshot.snapshot_id
    )

    assert (
        pointer.runtime_config_sha256
        == snapshot.content_sha256
    )

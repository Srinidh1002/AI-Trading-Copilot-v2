import json
from dataclasses import replace
from datetime import datetime, timezone

from dashboard.dashboard_read_model_state import (
    recover_task9_durable_authorities,
)
from services.certification.task9_external_provider_blocker import (
    Task9ExternalProviderBlockerStore,
)
from services.dashboard_read_models import DashboardApplicationViewV1
from services.contracts.task9_dashboard_active_campaign_projection_v1 import (
    Task9DashboardActiveCampaignProjectionV1,
)
from services.dashboard_publication.task9_dashboard_active_campaign_projection_store import (
    Task9DashboardActiveCampaignProjectionStore,
)
from services.contracts.task9_live_paper_certification_progress_v1 import (
    Task9LivePaperCertificationProgressV1,
    Task9MarketProgressV1,
)


NOW = datetime(
    2026,
    8,
    11,
    3,
    47,
    27,
    tzinfo=timezone.utc,
)


def _write_manifest(
    root,
    run_id="run",
):
    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        root
        / "task9-live-paper-run.json"
    ).write_text(
        json.dumps(
            {
                "official_run_id": run_id,
                "official_start_at": (
                    NOW.isoformat()
                ),
                "execution_mode": "PAPER",
                "broker_order_submission": False,
                "live_execution_eligible": False,
            }
        ),
        encoding="utf-8",
    )

    Task9DashboardActiveCampaignProjectionStore(
        root
    ).save(
        Task9DashboardActiveCampaignProjectionV1(
            campaign_id=(
                "task924-dashboard-campaign"
            ),
            active_market_date=(
                NOW.date()
            ),
            active_official_run_id=(
                run_id
            ),
            runtime_config_snapshot_id=(
                "task924-runtime-config"
            ),
            runtime_config_sha256=(
                "a" * 64
            ),
            projected_at=NOW,
        )
    )


def _write_empty_progress_authority(
    root,
    run_id="run",
):
    del run_id

    progress = (
        Task9LivePaperCertificationProgressV1(
            nifty=Task9MarketProgressV1(
                "NIFTY",
                100,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ),
            sensex=Task9MarketProgressV1(
                "SENSEX",
                100,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ),
            replay_excluded=0,
            duplicate_excluded=0,
            invalid_excluded=0,
            unresolved=0,
            certification_complete=False,
        )
    )

    (
        root
        / "task9-live-paper-certification-progress.json"
    ).write_text(
        json.dumps(
            progress.to_dict()
        ),
        encoding="utf-8",
    )


def _progress():
    return (
        Task9LivePaperCertificationProgressV1(
            nifty=Task9MarketProgressV1(
                "NIFTY",
                100,
                4,
                1,
                3,
                2,
                1,
                6,
                4,
                2,
            ),
            sensex=Task9MarketProgressV1(
                "SENSEX",
                100,
                7,
                2,
                5,
                3,
                2,
                8,
                5,
                3,
            ),
            replay_excluded=1,
            duplicate_excluded=2,
            invalid_excluded=3,
            unresolved=4,
            certification_complete=False,
        )
    )


def _write_current_progress(
    root,
    progress=None,
):
    (
        root
        / "task9-live-paper-certification-progress.json"
    ).write_text(
        json.dumps(
            (
                progress
                or _progress()
            ).to_dict()
        ),
        encoding="utf-8",
    )


def _write_legacy_current_progress(
    root,
    progress=None,
):
    raw = (
        progress
        or _progress()
    ).to_dict()

    for market in (
        "nifty",
        "sensex",
    ):
        raw[market].pop(
            "wait_completed"
        )
        raw[market].pop(
            "wait_passed"
        )
        raw[market].pop(
            "wait_failed"
        )

    (
        root
        / "task9-live-paper-certification-progress.json"
    ).write_text(
        json.dumps(raw),
        encoding="utf-8",
    )


def _publication_without_live_detail():
    return DashboardApplicationViewV1(
        "publication-without-detail",
        NOW,
        "PUBLISHED_RUNTIME_STATE",
        blockers=(
            "LIVE_DETAIL_NOT_PUBLISHED_BY_RUNNER",
        ),
    )


def test_recovers_zero_progress_and_active_provider_blocker_without_live_detail(
    tmp_path,
):
    root = (
        tmp_path
        / "certified_runtime"
        / "task9"
    )

    _write_manifest(root)
    _write_empty_progress_authority(
        root
    )

    blocker = (
        Task9ExternalProviderBlockerStore(
            root
        ).record(
            "run",
            observed_at=NOW,
        )
    )

    recovered = (
        recover_task9_durable_authorities(
            _publication_without_live_detail(),
            persistence_root=root,
        )
    )

    assert (
        recovered
        .task9_certification_progress
        .nifty
        .completed_live_paper_trades,
        recovered
        .task9_certification_progress
        .nifty
        .target_trade_count,
        recovered
        .task9_certification_progress
        .sensex
        .completed_live_paper_trades,
        recovered
        .task9_certification_progress
        .sensex
        .target_trade_count,
    ) == (
        0,
        100,
        0,
        100,
    )

    assert (
        recovered
        .task9_certification_progress
        .nifty
        .wait_completed
        == 0
    )

    assert (
        recovered
        .task9_certification_progress
        .sensex
        .wait_completed
        == 0
    )

    assert (
        recovered
        .external_provider_blocker[
            "status"
        ]
        == "ACTIVE"
    )

    assert (
        recovered
        .external_provider_blocker[
            "blocker_code"
        ]
        == blocker["blocker_code"]
    )

    assert (
        recovered
        .external_provider_blocker[
            "last_failure_reason"
        ]
        == (
            "HISTORICAL-DATA_RATE_LIMITED"
        )
    )

    assert (
        recovered
        .external_provider_blocker[
            "consecutive_rate_limit_count"
        ]
        == 1
    )

    assert (
        "LIVE_DETAIL_NOT_PUBLISHED_BY_RUNNER"
        in recovered.blockers
    )


def test_missing_durable_authority_fails_closed_without_synthesizing_progress(
    tmp_path,
):
    recovered = (
        recover_task9_durable_authorities(
            _publication_without_live_detail(),
            persistence_root=(
                tmp_path
                / "task9"
            ),
        )
    )

    assert (
        recovered.task9_certification_progress
        is None
    )

    assert (
        recovered.external_provider_blocker
        is None
    )


def test_restart_recovery_is_read_only_and_preserves_durable_files(
    tmp_path,
):
    root = (
        tmp_path
        / "certified_runtime"
        / "task9"
    )

    _write_manifest(root)
    _write_empty_progress_authority(
        root
    )

    Task9ExternalProviderBlockerStore(
        root
    ).record(
        "run",
        observed_at=NOW,
    )

    files = (
        root
        / "task9-live-paper-run.json",
        root
        / "task9-live-paper-certification-progress.json",
        root
        / "task9-external-provider-blocker.json",
    )

    before = {
        path: path.read_bytes()
        for path in files
    }

    first = (
        recover_task9_durable_authorities(
            _publication_without_live_detail(),
            persistence_root=root,
        )
    )

    restarted = (
        recover_task9_durable_authorities(
            _publication_without_live_detail(),
            persistence_root=root,
        )
    )

    assert restarted == first

    assert {
        path: path.read_bytes()
        for path in files
    } == before

    assert (
        first.execution_mode
        == "PAPER"
    )

    assert (
        first.broker_order_submission
        is False
    )

    assert (
        first.live_execution_eligible
        is False
    )

    assert first.read_only is True


def test_current_progress_is_primary_typed_authority_and_preserves_counters(
    tmp_path,
):
    root = (
        tmp_path
        / "certified_runtime"
        / "task9"
    )

    _write_manifest(root)

    expected = _progress()

    _write_current_progress(
        root,
        expected,
    )

    recovered = (
        recover_task9_durable_authorities(
            _publication_without_live_detail(),
            persistence_root=root,
        )
    )

    assert (
        recovered
        .task9_certification_progress
        == expected
    )

    assert (
        recovered
        .task9_certification_progress
        .nifty
        .wait_completed,
        recovered
        .task9_certification_progress
        .nifty
        .wait_passed,
        recovered
        .task9_certification_progress
        .nifty
        .wait_failed,
    ) == (
        6,
        4,
        2,
    )

    assert (
        recovered
        .task9_certification_progress
        .sensex
        .wait_completed,
        recovered
        .task9_certification_progress
        .sensex
        .wait_passed,
        recovered
        .task9_certification_progress
        .sensex
        .wait_failed,
    ) == (
        8,
        5,
        3,
    )


def test_legacy_progress_recovers_with_zero_wait_analytics(
    tmp_path,
):
    root = (
        tmp_path
        / "certified_runtime"
        / "task9"
    )

    _write_manifest(root)

    _write_legacy_current_progress(
        root
    )

    recovered = (
        recover_task9_durable_authorities(
            _publication_without_live_detail(),
            persistence_root=root,
        )
    )

    progress = (
        recovered
        .task9_certification_progress
    )

    assert progress is not None

    assert (
        progress.nifty.wait_completed,
        progress.nifty.wait_passed,
        progress.nifty.wait_failed,
    ) == (
        0,
        0,
        0,
    )

    assert (
        progress.sensex.wait_completed,
        progress.sensex.wait_passed,
        progress.sensex.wait_failed,
    ) == (
        0,
        0,
        0,
    )

    assert (
        progress.nifty.completed_live_paper_trades
        == 4
    )

    assert (
        progress.sensex.completed_live_paper_trades
        == 7
    )


def test_mixed_wait_progress_shape_fails_closed(
    tmp_path,
):
    root = (
        tmp_path
        / "certified_runtime"
        / "task9"
    )

    _write_manifest(root)

    raw = _progress().to_dict()

    raw["nifty"].pop(
        "wait_failed"
    )

    (
        root
        / "task9-live-paper-certification-progress.json"
    ).write_text(
        json.dumps(raw),
        encoding="utf-8",
    )

    recovered = (
        recover_task9_durable_authorities(
            _publication_without_live_detail(),
            persistence_root=root,
        )
    )

    assert (
        recovered.task9_certification_progress
        is None
    )


def test_malformed_current_progress_fails_closed_and_never_overwrites_existing_view(
    tmp_path,
):
    root = (
        tmp_path
        / "certified_runtime"
        / "task9"
    )

    _write_manifest(root)

    (
        root
        / "task9-live-paper-certification-progress.json"
    ).write_text(
        "{}",
        encoding="utf-8",
    )

    shell = (
        _publication_without_live_detail()
    )

    assert (
        recover_task9_durable_authorities(
            shell,
            persistence_root=root,
        ).task9_certification_progress
        is None
    )

    existing = replace(
        shell,
        task9_certification_progress=(
            _progress()
        ),
    )

    assert (
        recover_task9_durable_authorities(
            existing,
            persistence_root=root,
        )
        == existing
    )

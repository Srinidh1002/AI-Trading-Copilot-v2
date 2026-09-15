"""Task 9.98A campaign/run coherence for durable dashboard progress."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timezone

from services.contracts.task9_dashboard_active_campaign_projection_v1 import (
    Task9DashboardActiveCampaignProjectionV1,
)
from services.contracts.task9_live_paper_certification_progress_v1 import (
    Task9LivePaperCertificationProgressV1,
    Task9MarketProgressV1,
)
from services.dashboard_publication.task9_dashboard_active_campaign_projection_store import (
    Task9DashboardActiveCampaignProjectionStore,
)
from services.dashboard_read_models import (
    DashboardApplicationViewV1,
)
from services.dashboard_read_models.task9_durable_authority_recovery import (
    recover_task9_durable_authorities,
)


NOW = datetime(
    2026,
    8,
    18,
    5,
    30,
    tzinfo=timezone.utc,
)

DAY = date(
    2026,
    8,
    18,
)


def _write_manifest(
    root,
    *,
    run_id="run-current",
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


def _progress():
    return Task9LivePaperCertificationProgressV1(
        nifty=Task9MarketProgressV1(
            market="NIFTY",
            target_trade_count=100,
            completed_live_paper_trades=11,
            pending_entered_trades=1,
            no_trade_completed=2,
            no_trade_passed=1,
            no_trade_failed=1,
            wait_completed=3,
            wait_passed=2,
            wait_failed=1,
        ),
        sensex=Task9MarketProgressV1(
            market="SENSEX",
            target_trade_count=100,
            completed_live_paper_trades=8,
            pending_entered_trades=2,
            no_trade_completed=4,
            no_trade_passed=3,
            no_trade_failed=1,
            wait_completed=5,
            wait_passed=4,
            wait_failed=1,
        ),
        replay_excluded=1,
        duplicate_excluded=2,
        invalid_excluded=3,
        unresolved=4,
        certification_complete=False,
    )


def _write_progress(
    root,
):
    (
        root
        / "task9-live-paper-certification-progress.json"
    ).write_text(
        json.dumps(
            _progress().to_dict()
        ),
        encoding="utf-8",
    )


def _projection(
    *,
    run_id="run-current",
):
    return Task9DashboardActiveCampaignProjectionV1(
        campaign_id="campaign-current",
        active_market_date=DAY,
        active_official_run_id=run_id,
        runtime_config_snapshot_id=(
            "snapshot-current"
        ),
        runtime_config_sha256=(
            "a" * 64
        ),
        projected_at=NOW,
    )


def _write_projection(
    root,
    *,
    run_id="run-current",
):
    Task9DashboardActiveCampaignProjectionStore(
        root
    ).save(
        _projection(
            run_id=run_id
        )
    )


def _shell(
    *,
    progress=None,
):
    return DashboardApplicationViewV1(
        view_id="task998a-shell",
        generated_at=NOW,
        market_session_state=(
            "PUBLISHED_RUNTIME_STATE"
        ),
        task9_certification_progress=progress,
    )


def test_matching_active_campaign_exposes_persisted_progress(
    tmp_path,
):
    _write_manifest(
        tmp_path
    )
    _write_progress(
        tmp_path
    )
    _write_projection(
        tmp_path
    )

    recovered = (
        recover_task9_durable_authorities(
            _shell(),
            persistence_root=tmp_path,
        )
    )

    assert (
        recovered.task9_certification_progress
        == _progress()
    )


def test_missing_active_campaign_projection_suppresses_progress(
    tmp_path,
):
    _write_manifest(
        tmp_path
    )
    _write_progress(
        tmp_path
    )

    recovered = (
        recover_task9_durable_authorities(
            _shell(),
            persistence_root=tmp_path,
        )
    )

    assert (
        recovered.task9_certification_progress
        is None
    )


def test_mismatched_active_run_suppresses_persisted_progress(
    tmp_path,
):
    _write_manifest(
        tmp_path,
        run_id="run-current",
    )
    _write_progress(
        tmp_path
    )
    _write_projection(
        tmp_path,
        run_id="run-stale",
    )

    recovered = (
        recover_task9_durable_authorities(
            _shell(),
            persistence_root=tmp_path,
        )
    )

    assert (
        recovered.task9_certification_progress
        is None
    )


def test_mismatched_active_run_removes_progress_already_present_in_view(
    tmp_path,
):
    _write_manifest(
        tmp_path,
        run_id="run-current",
    )
    _write_projection(
        tmp_path,
        run_id="run-stale",
    )

    recovered = (
        recover_task9_durable_authorities(
            _shell(
                progress=_progress()
            ),
            persistence_root=tmp_path,
        )
    )

    assert (
        recovered.task9_certification_progress
        is None
    )


def test_matching_campaign_preserves_progress_already_present_in_view(
    tmp_path,
):
    _write_manifest(
        tmp_path
    )
    _write_projection(
        tmp_path
    )

    expected = _progress()

    source = _shell(
        progress=expected
    )

    recovered = (
        recover_task9_durable_authorities(
            source,
            persistence_root=tmp_path,
        )
    )

    assert (
        recovered.task9_certification_progress
        is expected
    )


def test_corrupt_projection_fails_closed_for_progress(
    tmp_path,
):
    _write_manifest(
        tmp_path
    )
    _write_progress(
        tmp_path
    )

    (
        tmp_path
        / "task9-dashboard-active-campaign.json"
    ).write_text(
        "{}",
        encoding="utf-8",
    )

    recovered = (
        recover_task9_durable_authorities(
            _shell(),
            persistence_root=tmp_path,
        )
    )

    assert (
        recovered.task9_certification_progress
        is None
    )


def test_campaign_mismatch_does_not_mutate_durable_files(
    tmp_path,
):
    _write_manifest(
        tmp_path,
        run_id="run-current",
    )
    _write_progress(
        tmp_path
    )
    _write_projection(
        tmp_path,
        run_id="run-stale",
    )

    paths = (
        tmp_path
        / "task9-live-paper-run.json",
        tmp_path
        / "task9-live-paper-certification-progress.json",
        tmp_path
        / "task9-dashboard-active-campaign.json",
    )

    before = {
        path: path.read_bytes()
        for path in paths
    }

    recover_task9_durable_authorities(
        _shell(
            progress=_progress()
        ),
        persistence_root=tmp_path,
    )

    after = {
        path: path.read_bytes()
        for path in paths
    }

    assert after == before

from datetime import datetime, date, timedelta, timezone
import json

import pytest

from services.certification.task9_live_paper_certification_launcher import (
    load_or_create_task9_run_manifest,
)


IST = timezone(
    timedelta(
        hours=5,
        minutes=30,
    )
)

CAMPAIGN = "campaign-r2"

OLD_RUN = "task9-live-20260819-r2"
NEW_RUN = "task9-live-20260820-r2"

OLD_DATE = date(2026, 8, 19)
NEW_DATE = date(2026, 8, 20)

OLD_SHA = "a" * 64
NEW_SHA = "b" * 64

OLD_SNAPSHOT = (
    "task9-runtime-config-" + OLD_SHA
)
NEW_SNAPSHOT = (
    "task9-runtime-config-" + NEW_SHA
)


def _seed_old(root):
    return load_or_create_task9_run_manifest(
        persistence_root=root,
        official_run_id=OLD_RUN,
        started_at=datetime(
            2026,
            8,
            19,
            9,
            20,
            tzinfo=IST,
        ),
        runtime_config_snapshot_id=(
            OLD_SNAPSHOT
        ),
        runtime_config_sha256=OLD_SHA,
        campaign_id=CAMPAIGN,
        market_date=OLD_DATE,
    )


def _write_target_authorities(
    root,
    *,
    campaign_id=CAMPAIGN,
    run_id=NEW_RUN,
    market_date=NEW_DATE,
    snapshot_id=NEW_SNAPSHOT,
    sha256=NEW_SHA,
):
    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        root / "active-campaign.json"
    ).write_text(
        json.dumps(
            {
                "status": "ACTIVE",
                "campaign_id": campaign_id,
                "active_market_date": (
                    market_date.isoformat()
                ),
                "active_official_run_id": (
                    run_id
                ),
                "runtime_config_snapshot_id": (
                    snapshot_id
                ),
                "runtime_config_sha256": (
                    sha256
                ),
            }
        ),
        encoding="utf-8",
    )

    manifests = (
        root / "official-run-manifests"
    )
    manifests.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        manifests / f"{run_id}.json"
    ).write_text(
        json.dumps(
            {
                "official_run_id": run_id,
                "official_start_at": (
                    "2026-08-20T09:30:00+05:30"
                ),
                "campaign_id": campaign_id,
                "market_date": (
                    market_date.isoformat()
                ),
                "run_classification": (
                    "OFFICIAL_CERTIFICATION"
                ),
                "runtime_config_snapshot_id": (
                    snapshot_id
                ),
                "runtime_config_sha256": (
                    sha256
                ),
                "execution_mode": "PAPER",
                "broker_order_submission": False,
                "live_execution_eligible": False,
            }
        ),
        encoding="utf-8",
    )


def _advance(root, **kwargs):
    values = {
        "persistence_root": root,
        "official_run_id": NEW_RUN,
        "started_at": datetime(
            2026,
            8,
            20,
            9,
            45,
            tzinfo=IST,
        ),
        "runtime_config_snapshot_id": (
            NEW_SNAPSHOT
        ),
        "runtime_config_sha256": NEW_SHA,
        "campaign_id": CAMPAIGN,
        "market_date": NEW_DATE,
    }
    values.update(kwargs)

    return (
        load_or_create_task9_run_manifest(
            **values
        )
    )


def test_canonical_cross_day_rollover_advances_singleton(tmp_path):
    root = tmp_path / "task9"

    old = _seed_old(root)
    _write_target_authorities(root)

    advanced = _advance(root)

    assert old.official_run_id == OLD_RUN
    assert advanced.official_run_id == NEW_RUN
    assert advanced.market_date == NEW_DATE
    assert (
        advanced.runtime_config_snapshot_id
        == NEW_SNAPSHOT
    )

    durable = json.loads(
        (
            root
            / "task9-live-paper-run.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert (
        durable["official_run_id"]
        == NEW_RUN
    )
    assert (
        durable["market_date"]
        == "2026-08-20"
    )


def test_same_run_restart_remains_strict_on_provenance(tmp_path):
    root = tmp_path / "task9"

    _seed_old(root)

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_RUNTIME_CONFIG_"
            "PROVENANCE_MISMATCH"
        ),
    ):
        load_or_create_task9_run_manifest(
            persistence_root=root,
            official_run_id=OLD_RUN,
            started_at=datetime(
                2026,
                8,
                19,
                10,
                0,
                tzinfo=IST,
            ),
            runtime_config_snapshot_id=(
                NEW_SNAPSHOT
            ),
            runtime_config_sha256=NEW_SHA,
            campaign_id=CAMPAIGN,
            market_date=OLD_DATE,
        )


def test_cross_day_without_canonical_authorities_fails_closed(tmp_path):
    root = tmp_path / "task9"

    _seed_old(root)

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_OFFICIAL_RUN_ID_"
            "MISMATCH"
        ),
    ):
        _advance(root)


def test_cross_day_different_campaign_fails_closed(tmp_path):
    root = tmp_path / "task9"

    _seed_old(root)

    _write_target_authorities(
        root,
        campaign_id="other-campaign",
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_OFFICIAL_RUN_ID_"
            "MISMATCH"
        ),
    ):
        _advance(root)


def test_cross_day_wrong_target_snapshot_fails_closed(tmp_path):
    root = tmp_path / "task9"

    _seed_old(root)

    _write_target_authorities(
        root,
        snapshot_id=(
            "task9-runtime-config-"
            + ("c" * 64)
        ),
        sha256="c" * 64,
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_OFFICIAL_RUN_ID_"
            "MISMATCH"
        ),
    ):
        _advance(root)


def test_cross_day_cannot_move_backward_or_same_date(tmp_path):
    root = tmp_path / "task9"

    _seed_old(root)

    same_run_target = (
        "task9-live-other-run"
    )

    _write_target_authorities(
        root,
        run_id=same_run_target,
        market_date=OLD_DATE,
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_OFFICIAL_RUN_ID_"
            "MISMATCH"
        ),
    ):
        _advance(
            root,
            official_run_id=(
                same_run_target
            ),
            market_date=OLD_DATE,
        )

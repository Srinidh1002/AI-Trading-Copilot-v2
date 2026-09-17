from datetime import date, datetime, timezone

import pytest

from services.certification.task9_live_paper_certification_launcher import (
    Task9LivePaperRunManifestV1,
)
from services.certification.task9_official_run_manifest_store import (
    Task9OfficialRunManifestStore,
)


NOW = datetime(
    2026,
    8,
    19,
    4,
    45,
    tzinfo=timezone.utc,
)

SHA = "a" * 64
SID = "task9-runtime-config-" + SHA


def _manifest(
    run_id="task9-live-20260819-r2",
):
    return Task9LivePaperRunManifestV1(
        official_run_id=run_id,
        official_start_at=NOW,
        runtime_config_snapshot_id=SID,
        runtime_config_sha256=SHA,
        campaign_id=(
            "task9-live-certification-2026-08-18-r2"
        ),
        market_date=date(
            2026,
            8,
            19,
        ),
    )


def test_keyed_official_run_store_is_idempotent(
    tmp_path,
):
    store = Task9OfficialRunManifestStore(
        tmp_path
    )

    value = _manifest()

    assert store.save(value) == value
    assert store.save(value) == value
    assert store.get(
        value.official_run_id
    ) == value


def test_keyed_official_run_store_rejects_conflict(
    tmp_path,
):
    store = Task9OfficialRunManifestStore(
        tmp_path
    )

    first = _manifest()

    store.save(first)

    conflict = Task9LivePaperRunManifestV1(
        official_run_id=(
            first.official_run_id
        ),
        official_start_at=NOW,
        runtime_config_snapshot_id=(
            "task9-runtime-config-"
            + ("b" * 64)
        ),
        runtime_config_sha256=(
            "b" * 64
        ),
        campaign_id=(
            first.campaign_id
        ),
        market_date=(
            first.market_date
        ),
    )

    with pytest.raises(
        ValueError,
        match="conflicting Task 9 official run manifest",
    ):
        store.save(
            conflict
        )


@pytest.mark.parametrize(
    "run_id",
    (
        "../bad",
        "bad/run",
        "bad\\run",
        "",
    ),
)
def test_keyed_official_run_store_rejects_unsafe_ids(
    tmp_path,
    run_id,
):
    store = Task9OfficialRunManifestStore(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="official_run_id",
    ):
        store.get(
            run_id
        )

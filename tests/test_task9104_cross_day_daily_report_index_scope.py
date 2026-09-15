from datetime import datetime, timezone
import json

from services.certification.task9_certification_publication import (
    Task9CertificationPublicationAuthority,
)
from services.certification.task9_daily_report_index import (
    Task9DailyReportIndex,
)
import services.certification.task9_daily_report_index_scope as scope


AUG18_RUN = "task9-live-20260818-r2"
AUG19_RUN = "task9-live-20260819-r2"
CAMPAIGN = "task9-live-certification-2026-08-18-r2"


def _manifest(root, run_id, market_date):
    directory = root / "official-run-manifests"
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    (directory / f"{run_id}.json").write_text(
        json.dumps(
            {
                "official_run_id": run_id,
                "campaign_id": CAMPAIGN,
                "market_date": market_date,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _index(path, run_id, session_date):
    value = Task9DailyReportIndex(
        official_run_id=run_id,
        file_path=path,
    )

    value.save(
        report_id=f"report:{run_id}:{session_date}",
        session_date=session_date,
        semantic_hash="a" * 64,
        archive_path=(
            f"daily/{session_date}/"
            f"report-{run_id}.json"
        ),
    )

    return value


def test_current_run_uses_run_scoped_index_without_mutating_legacy(
    tmp_path,
):
    legacy = tmp_path / "daily-report-index.json"

    _index(
        legacy,
        AUG18_RUN,
        "2026-08-18",
    )

    before = legacy.read_bytes()

    authority = Task9CertificationPublicationAuthority(
        official_run_id=AUG19_RUN,
        official_start_at=datetime(
            2026,
            8,
            19,
            4,
            0,
            tzinfo=timezone.utc,
        ),
        root=tmp_path,
        prediction_ledger=object(),
        binding_store=object(),
        outcome_store=object(),
        reconciliation_store=object(),
        trade_persistence_service=object(),
        starting_capital=10_000.0,
    )

    expected = scope.task9_daily_report_index_path(
        tmp_path,
        AUG19_RUN,
    )

    assert authority.index.file_path == expected
    assert authority.index.official_run_id == AUG19_RUN
    assert legacy.read_bytes() == before
    assert expected != legacy


def test_previous_run_resolver_accepts_matching_legacy_index(
    tmp_path,
):
    legacy = tmp_path / "daily-report-index.json"

    _index(
        legacy,
        AUG18_RUN,
        "2026-08-18",
    )

    recovered = (
        scope.open_task9_daily_report_index_for_run(
            root=tmp_path,
            official_run_id=AUG18_RUN,
        )
    )

    assert recovered.official_run_id == AUG18_RUN
    assert recovered.file_path == legacy


def test_campaign_progress_aggregates_legacy_and_current_run_scoped_indexes(
    tmp_path,
    monkeypatch,
):
    _manifest(
        tmp_path,
        AUG18_RUN,
        "2026-08-18",
    )
    _manifest(
        tmp_path,
        AUG19_RUN,
        "2026-08-19",
    )

    legacy = tmp_path / "daily-report-index.json"

    _index(
        legacy,
        AUG18_RUN,
        "2026-08-18",
    )

    current = scope.task9_daily_report_index_path(
        tmp_path,
        AUG19_RUN,
    )

    _index(
        current,
        AUG19_RUN,
        "2026-08-19",
    )

    reports = {
        AUG18_RUN: {
            "session_date": "2026-08-18",
            "report_id": "aug18-report",
        },
        AUG19_RUN: {
            "session_date": "2026-08-19",
            "report_id": "aug19-report",
        },
    }

    def fake_recover(
        *,
        index,
        official_run_id,
        archive_root,
    ):
        assert (
            index.official_run_id
            == official_run_id
        )

        return (
            reports[official_run_id],
        )

    monkeypatch.setattr(
        scope,
        "recover_task9_daily_reports",
        fake_recover,
    )

    recovered = (
        scope.recover_task9_campaign_daily_reports(
            root=tmp_path,
            current_official_run_id=AUG19_RUN,
            archive_root=(
                tmp_path
                / "certification_reports"
            ),
        )
    )

    assert tuple(
        item["session_date"]
        for item in recovered
    ) == (
        "2026-08-18",
        "2026-08-19",
    )


def test_campaign_aggregation_ignores_other_campaign_run(
    tmp_path,
    monkeypatch,
):
    _manifest(
        tmp_path,
        AUG19_RUN,
        "2026-08-19",
    )

    other_run = "task9-other-campaign-run"

    directory = (
        tmp_path
        / "official-run-manifests"
    )

    (directory / f"{other_run}.json").write_text(
        json.dumps(
            {
                "official_run_id": other_run,
                "campaign_id": "other-campaign",
                "market_date": "2026-08-19",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    _index(
        scope.task9_daily_report_index_path(
            tmp_path,
            AUG19_RUN,
        ),
        AUG19_RUN,
        "2026-08-19",
    )

    _index(
        scope.task9_daily_report_index_path(
            tmp_path,
            other_run,
        ),
        other_run,
        "2026-08-19",
    )

    calls = []

    def fake_recover(
        *,
        index,
        official_run_id,
        archive_root,
    ):
        calls.append(
            official_run_id
        )

        return (
            {
                "session_date": "2026-08-19",
                "report_id": official_run_id,
            },
        )

    monkeypatch.setattr(
        scope,
        "recover_task9_daily_reports",
        fake_recover,
    )

    recovered = (
        scope.recover_task9_campaign_daily_reports(
            root=tmp_path,
            current_official_run_id=AUG19_RUN,
            archive_root=(
                tmp_path
                / "certification_reports"
            ),
        )
    )

    assert calls == [AUG19_RUN]
    assert len(recovered) == 1


def test_cross_run_same_session_conflict_fails_closed(
    tmp_path,
    monkeypatch,
):
    _manifest(
        tmp_path,
        AUG18_RUN,
        "2026-08-18",
    )
    _manifest(
        tmp_path,
        AUG19_RUN,
        "2026-08-19",
    )

    _index(
        tmp_path / "daily-report-index.json",
        AUG18_RUN,
        "2026-08-18",
    )

    _index(
        scope.task9_daily_report_index_path(
            tmp_path,
            AUG19_RUN,
        ),
        AUG19_RUN,
        "2026-08-18",
    )

    def fake_recover(
        *,
        index,
        official_run_id,
        archive_root,
    ):
        return (
            {
                "session_date": "2026-08-18",
                "report_id": official_run_id,
            },
        )

    monkeypatch.setattr(
        scope,
        "recover_task9_daily_reports",
        fake_recover,
    )

    import pytest

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_CROSS_RUN_DAILY_REPORT_CONFLICT"
        ),
    ):
        scope.recover_task9_campaign_daily_reports(
            root=tmp_path,
            current_official_run_id=AUG19_RUN,
            archive_root=(
                tmp_path
                / "certification_reports"
            ),
        )

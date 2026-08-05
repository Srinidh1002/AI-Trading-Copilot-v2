from dataclasses import replace
from pathlib import Path

import pytest

from services.reporting.prediction_performance_report_archive import (
    PredictionPerformanceReportArchive,
)
from test_r71_prediction_performance_report_v1 import (
    report,
)


def test_json_and_text_exports_are_deterministic(tmp_path):
    archive = PredictionPerformanceReportArchive(
        tmp_path
    )
    value = report()

    first = archive.save(value)
    first_json = Path(
        first["json_path"]
    ).read_text(encoding="utf-8")
    first_text = Path(
        first["text_path"]
    ).read_text(encoding="utf-8")

    second = archive.save(value)

    assert Path(
        second["json_path"]
    ).read_text(encoding="utf-8") == first_json
    assert Path(
        second["text_path"]
    ).read_text(encoding="utf-8") == first_text
    assert archive.load_json(
        value.report_id
    ) == value.to_dict()


def test_export_is_paper_only_and_read_only(tmp_path):
    result = PredictionPerformanceReportArchive(
        tmp_path
    ).save(report())

    assert result["execution_mode"] == "PAPER"
    assert result["live_execution_eligible"] is False
    assert result["broker_order_submission"] is False
    assert result["read_only"] is True


def test_unsafe_report_identity_is_rejected(tmp_path):
    archive = PredictionPerformanceReportArchive(
        tmp_path
    )

    with pytest.raises(ValueError):
        archive.save(
            replace(
                report(),
                report_id="../escape",
            )
        )


def test_json_write_failure_leaves_no_partial_files(
    tmp_path,
    monkeypatch,
):
    archive = PredictionPerformanceReportArchive(
        tmp_path
    )

    def fail(*args, **kwargs):
        raise OSError("injected failure")

    monkeypatch.setattr(
        archive,
        "_atomic_write",
        fail,
    )

    with pytest.raises(OSError):
        archive.save(report())

    assert list(tmp_path.iterdir()) == []


def test_second_export_failure_restores_prior_json(
    tmp_path,
    monkeypatch,
):
    archive = PredictionPerformanceReportArchive(
        tmp_path
    )
    original = report()
    archive.save(original)

    changed = replace(
        original,
        generated_at=original.generated_at.replace(
            minute=1
        ),
    )
    original_json = (
        tmp_path
        / f"{original.report_id}.json"
    ).read_text(encoding="utf-8")

    real = archive._atomic_write
    calls = {"count": 0}

    def fail_second(target, content):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("text write failed")
        return real(target, content)

    monkeypatch.setattr(
        archive,
        "_atomic_write",
        fail_second,
    )

    with pytest.raises(OSError):
        archive.save(changed)

    assert (
        tmp_path
        / f"{original.report_id}.json"
    ).read_text(encoding="utf-8") == original_json


def test_render_text_has_stable_market_sections():
    text = (
        PredictionPerformanceReportArchive
        .render_text(report())
    )

    assert "\nOverall\n" in text
    assert "\nNIFTY\n" in text
    assert "\nSENSEX\n" in text
    assert "Broker Order Submission: False" in text

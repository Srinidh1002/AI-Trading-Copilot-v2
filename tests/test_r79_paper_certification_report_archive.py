from dataclasses import replace
from datetime import timedelta

import pytest

from services.reporting.paper_certification_report_archive import (
    PaperCertificationReportArchive,
)
from tests.r79_reporting_helpers import build_daily


def test_archive_is_atomic_write_once_and_duplicate_safe(tmp_path):
    report = build_daily()
    archive = PaperCertificationReportArchive(tmp_path)

    first = archive.save(report)
    second = archive.save(report)

    assert first["status"] == "SAVED"
    assert first["saved"] is True
    assert second["status"] == "DUPLICATE_SAME_PAYLOAD"
    assert second["saved"] is False
    assert archive.load_raw(report) == report.to_dict()


def test_archive_rejects_conflicting_same_report_id(tmp_path):
    report = build_daily()
    archive = PaperCertificationReportArchive(tmp_path)
    archive.save(report)

    changed = replace(
        report,
        generated_at=report.generated_at
        + timedelta(seconds=1),
    )

    with pytest.raises(
        ValueError,
        match="conflicting immutable",
    ):
        archive.save(changed)


@pytest.mark.parametrize(
    "report_id",
    ("../escape", r"C:\\escape", "", "bad/name"),
)
def test_archive_rejects_unsafe_report_ids(tmp_path, report_id):
    archive = PaperCertificationReportArchive(tmp_path)

    with pytest.raises(ValueError):
        report = replace(build_daily(), report_id=report_id)
        archive.save(report)

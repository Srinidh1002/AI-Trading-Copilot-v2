"""Deterministic Task 7 offline PAPER certification report runner."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from services.certification.offline_paper_certification_matrix import (
    build_offline_paper_certification_report,
)
from services.contracts.offline_paper_certification_v1 import (
    OfflinePaperCertificationReportV1,
)


def run_offline_paper_certification(
    *,
    report_id: str,
    generated_at: datetime,
    branch_name: str,
    commit_sha: str,
    output_path: str | Path,
    failed_check_ids: tuple[str, ...] = (),
    blocked_check_ids: tuple[str, ...] = (),
    additional_warnings: tuple[str, ...] = (),
) -> OfflinePaperCertificationReportV1:
    """Build and atomically persist one deterministic JSON report."""

    report = build_offline_paper_certification_report(
        report_id=report_id,
        generated_at=generated_at,
        branch_name=branch_name,
        commit_sha=commit_sha,
        failed_check_ids=failed_check_ids,
        blocked_check_ids=blocked_check_ids,
        additional_warnings=additional_warnings,
    )
    write_offline_paper_certification_report(
        report=report,
        output_path=output_path,
    )
    return report


def write_offline_paper_certification_report(
    *,
    report: OfflinePaperCertificationReportV1,
    output_path: str | Path,
) -> None:
    if type(report) is not OfflinePaperCertificationReportV1:
        raise TypeError("report")

    path = Path(output_path)
    if not path.name:
        raise ValueError("output_path")
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = _report_to_dict(report)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_offline_paper_certification_report(
    output_path: str | Path,
) -> dict[str, object]:
    path = Path(output_path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid certification report") from exc
    if not isinstance(value, dict):
        raise ValueError("invalid certification report")
    return value


def _report_to_dict(
    report: OfflinePaperCertificationReportV1,
) -> dict[str, object]:
    payload = asdict(report)
    payload["generated_at"] = report.generated_at.isoformat()
    payload["checks"] = [
        {
            **asdict(check),
            "evidence": list(check.evidence),
            "blockers": list(check.blockers),
            "warnings": list(check.warnings),
        }
        for check in report.checks
    ]
    payload["schema_version"] = report.SCHEMA_VERSION
    return payload

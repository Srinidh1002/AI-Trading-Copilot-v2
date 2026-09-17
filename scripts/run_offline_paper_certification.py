"""Run repository-level offline PAPER certification."""
from __future__ import annotations

from datetime import datetime, timezone

from services.certification.repository_offline_paper_certification_launcher import (
    DEFAULT_CERTIFICATION_REPORT_PATH,
    launch_repository_offline_paper_certification,
)


def main() -> int:
    report = launch_repository_offline_paper_certification(
        report_id="task-7-offline-paper-certification",
        clock=lambda: datetime.now(timezone.utc),
    )
    print(
        f"{report.overall_status}: "
        f"{report.passed_count} passed, "
        f"{report.failed_count} failed, "
        f"{report.blocked_count} blocked"
    )
    print(f"report: {DEFAULT_CERTIFICATION_REPORT_PATH}")

    if report.overall_status == "PASSED":
        return 0
    if report.overall_status == "FAILED":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

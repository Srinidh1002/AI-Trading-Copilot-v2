"""Repository-level launcher for offline PAPER certification."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
import subprocess

from services.certification.offline_paper_certification_runner import (
    run_offline_paper_certification,
)
from services.contracts.offline_paper_certification_v1 import (
    OfflinePaperCertificationReportV1,
)


DEFAULT_CERTIFICATION_REPORT_PATH = Path(
    "artifacts/certification/offline_paper_certification.json"
)

Clock = Callable[[], datetime]
GitReader = Callable[[tuple[str, ...]], str]


def _default_git_reader(arguments: tuple[str, ...]) -> str:
    completed = subprocess.run(
        ("git",) + arguments,
        check=True,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    if not value:
        raise ValueError("git command returned blank output")
    return value


def launch_repository_offline_paper_certification(
    *,
    report_id: str,
    clock: Clock,
    output_path: str | Path = DEFAULT_CERTIFICATION_REPORT_PATH,
    git_reader: GitReader = _default_git_reader,
    failed_check_ids: tuple[str, ...] = (),
    blocked_check_ids: tuple[str, ...] = (),
    additional_warnings: tuple[str, ...] = (),
) -> OfflinePaperCertificationReportV1:
    """Resolve local repository identity and write the certification report."""

    if not callable(clock):
        raise TypeError("clock")
    if not callable(git_reader):
        raise TypeError("git_reader")

    generated_at = clock()
    if not isinstance(generated_at, datetime):
        raise TypeError("clock must return datetime")
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("clock must return timezone-aware datetime")

    branch_name = git_reader(
        ("rev-parse", "--abbrev-ref", "HEAD"),
    ).strip()
    commit_sha = git_reader(
        ("rev-parse", "--short", "HEAD"),
    ).strip()
    if not branch_name:
        raise ValueError("branch_name")
    if not commit_sha:
        raise ValueError("commit_sha")

    return run_offline_paper_certification(
        report_id=report_id,
        generated_at=generated_at,
        branch_name=branch_name,
        commit_sha=commit_sha,
        output_path=output_path,
        failed_check_ids=failed_check_ids,
        blocked_check_ids=blocked_check_ids,
        additional_warnings=additional_warnings,
    )

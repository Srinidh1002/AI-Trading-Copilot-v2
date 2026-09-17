"""Repository launcher for complete Task 7A replay certification."""
from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from services.certification.complete_replay_certification_runner import (
    run_complete_replay_certification,
)
from services.certification.replay_certification_report import (
    ReplayCertificationReportV1,
    build_replay_certification_report,
)


DEFAULT_REPLAY_REPORT_PATH = Path(
    "artifacts/certification/task7a_replay_certification.json"
)
DEFAULT_REPLAY_WORK_ROOT = Path(
    "artifacts/certification/task7a_replay_work"
)

GitReader = Callable[[str], str]


def _git_reader(argument: str) -> str:
    completed = subprocess.run(
        ["git", *argument.split()],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def launch_repository_replay_certification(
    *,
    report_path: str | Path = DEFAULT_REPLAY_REPORT_PATH,
    work_root: str | Path = DEFAULT_REPLAY_WORK_ROOT,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    git_reader: GitReader = _git_reader,
) -> ReplayCertificationReportV1:
    generated_at = clock()
    if (
        not isinstance(generated_at, datetime)
        or generated_at.tzinfo is None
        or generated_at.utcoffset() is None
    ):
        raise ValueError("clock must return timezone-aware datetime")

    ledger = run_complete_replay_certification(
        work_root=work_root,
        ledger_id="task-7a-complete-replay-ledger",
        generated_at=generated_at,
    )
    report = build_replay_certification_report(
        ledger=ledger,
        report_id="task-7a-replay-certification",
        branch_name=git_reader(
            "rev-parse --abbrev-ref HEAD"
        ),
        commit_sha=git_reader(
            "rev-parse --short HEAD"
        ),
    )

    destination = Path(report_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )
    temporary.write_text(
        json.dumps(
            report.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    temporary.replace(destination)
    return report

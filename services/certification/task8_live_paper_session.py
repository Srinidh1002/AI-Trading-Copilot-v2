"""Bounded multi-cycle Task 8 live PAPER certification session."""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import sleep as default_sleep

from services.certification.task8_live_paper_canary import (
    Task8CanaryDependenciesV1,
    Task8CanaryReportV1,
    run_task8_live_paper_canary,
    write_task8_report,
)


Clock = Callable[[], datetime]
DependencyFactory = Callable[[], Task8CanaryDependenciesV1]
Sleep = Callable[[float], None]
IdFactory = Callable[[], str]


def _utc(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value.astimezone(timezone.utc)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name)
    return value.strip()


@dataclass(frozen=True, slots=True)
class Task8LivePaperSessionReportV1:
    """Aggregate evidence for one bounded Task 8 live PAPER session."""

    session_id: str
    started_at: datetime
    completed_at: datetime
    requested_cycle_count: int
    completed_cycle_count: int
    passed_cycle_count: int
    failed_cycle_count: int
    total_nifty_evaluation_count: int
    total_sensex_evaluation_count: int
    interval_seconds: float
    session_status: str
    branch: str
    commit: str
    cycle_run_ids: tuple[str, ...]
    cycle_report_paths: tuple[str, ...]
    blockers: tuple[str, ...]
    paper_mode: bool
    broker_submission_disabled: bool
    live_execution_ineligible: bool
    schema_version: str = "task8_live_paper_session_report.v1"

    def __post_init__(self) -> None:
        for name in ("session_id", "branch", "commit"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        started = _utc(self.started_at, "started_at")
        completed = _utc(self.completed_at, "completed_at")
        if started > completed:
            raise ValueError("started_at must not exceed completed_at")
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "completed_at", completed)

        for name in (
            "requested_cycle_count",
            "completed_cycle_count",
            "passed_cycle_count",
            "failed_cycle_count",
            "total_nifty_evaluation_count",
            "total_sensex_evaluation_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(name)

        if self.requested_cycle_count < 1:
            raise ValueError("requested_cycle_count")
        if self.completed_cycle_count > self.requested_cycle_count:
            raise ValueError("completed_cycle_count")
        if (
            self.passed_cycle_count + self.failed_cycle_count
            != self.completed_cycle_count
        ):
            raise ValueError("cycle status counts")
        if (
            self.total_nifty_evaluation_count
            != self.completed_cycle_count
            or self.total_sensex_evaluation_count
            != self.completed_cycle_count
        ):
            raise ValueError(
                "each completed cycle must retain one evaluation per market"
            )

        if (
            type(self.interval_seconds) not in (int, float)
            or isinstance(self.interval_seconds, bool)
            or self.interval_seconds < 0
        ):
            raise ValueError("interval_seconds")
        object.__setattr__(
            self,
            "interval_seconds",
            float(self.interval_seconds),
        )

        if self.session_status not in {
            "PASSED",
            "FAILED",
            "INTERRUPTED",
        }:
            raise ValueError("session_status")

        if not isinstance(self.cycle_run_ids, tuple):
            raise TypeError("cycle_run_ids")
        if not isinstance(self.cycle_report_paths, tuple):
            raise TypeError("cycle_report_paths")
        if not isinstance(self.blockers, tuple):
            raise TypeError("blockers")
        if (
            len(self.cycle_run_ids) != self.completed_cycle_count
            or len(self.cycle_report_paths)
            != self.completed_cycle_count
        ):
            raise ValueError("cycle evidence count")

        for value in (
            self.paper_mode,
            self.broker_submission_disabled,
            self.live_execution_ineligible,
        ):
            if type(value) is not bool:
                raise TypeError("safety flags")

        if (
            not self.paper_mode
            or not self.broker_submission_disabled
            or not self.live_execution_ineligible
        ):
            raise ValueError("session must remain PAPER-only")

        if (
            self.session_status == "PASSED"
            and (
                self.completed_cycle_count
                != self.requested_cycle_count
                or self.failed_cycle_count
                or self.blockers
            )
        ):
            raise ValueError("PASSED session is incomplete")

        if (
            self.session_status == "FAILED"
            and self.failed_cycle_count < 1
            and "SESSION_EXECUTION_EXCEPTION" not in self.blockers
        ):
            raise ValueError(
                "FAILED session requires a failed cycle "
                "or execution exception"
            )

        if self.schema_version != (
            "task8_live_paper_session_report.v1"
        ):
            raise ValueError("schema_version")

    @property
    def passed(self) -> bool:
        return (
            self.session_status == "PASSED"
            and not self.blockers
        )

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["started_at"] = self.started_at.isoformat()
        value["completed_at"] = self.completed_at.isoformat()
        value["cycle_run_ids"] = list(self.cycle_run_ids)
        value["cycle_report_paths"] = list(
            self.cycle_report_paths
        )
        value["blockers"] = list(self.blockers)
        return value

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def write_task8_session_report(
    report: Task8LivePaperSessionReportV1,
    output_path: Path,
) -> Path:
    """Write one immutable aggregate session report."""

    if type(report) is not Task8LivePaperSessionReportV1:
        raise TypeError("report")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        raise FileExistsError(
            f"immutable session report path already exists: {path}"
        )

    path.write_text(
        report.to_json() + "\n",
        encoding="utf-8",
    )
    return path


def run_task8_live_paper_session(
    *,
    dependency_factory: DependencyFactory,
    cycle_count: int,
    interval_seconds: float,
    output_directory: Path,
    clock: Clock,
    session_id_factory: IdFactory,
    sleep_function: Sleep = default_sleep,
) -> tuple[
    Task8LivePaperSessionReportV1,
    Path,
]:
    """Run a bounded exact-count Task 8 PAPER session.

    Every completed parent cycle writes one immutable canary report.
    A failed canary stops the session immediately. Keyboard interruption
    retains completed-cycle evidence and writes an interrupted summary.
    """

    if not callable(dependency_factory):
        raise TypeError("dependency_factory")
    if type(cycle_count) is not int or cycle_count < 1:
        raise ValueError("cycle_count")
    if (
        type(interval_seconds) not in (int, float)
        or isinstance(interval_seconds, bool)
        or interval_seconds < 0
    ):
        raise ValueError("interval_seconds")
    if not callable(clock):
        raise TypeError("clock")
    if not callable(session_id_factory):
        raise TypeError("session_id_factory")
    if not callable(sleep_function):
        raise TypeError("sleep_function")

    destination = Path(output_directory)
    session_id = _text(
        session_id_factory(),
        "session_id",
    )
    started_at = _utc(clock(), "started_at")

    reports: list[Task8CanaryReportV1] = []
    report_paths: list[Path] = []
    blockers: list[str] = []
    session_status = "PASSED"
    branch = "UNKNOWN"
    commit = "UNKNOWN"

    try:
        for cycle_number in range(1, cycle_count + 1):
            dependencies = dependency_factory()
            if type(dependencies) is not Task8CanaryDependenciesV1:
                raise TypeError(
                    "dependency_factory must return exact "
                    "Task8CanaryDependenciesV1"
                )

            if reports:
                if (
                    dependencies.branch != branch
                    or dependencies.commit != commit
                ):
                    raise RuntimeError(
                        "branch or commit changed during session"
                    )
            else:
                branch = dependencies.branch
                commit = dependencies.commit

            report = run_task8_live_paper_canary(
                dependencies
            )

            cycle_path = destination / (
                f"{session_id}-cycle-"
                f"{cycle_number:03d}-"
                f"{report.run_id}.json"
            )
            write_task8_report(
                report,
                cycle_path,
            )

            reports.append(report)
            report_paths.append(cycle_path)

            if not report.passed:
                session_status = "FAILED"
                blockers.append(
                    f"CYCLE_{cycle_number:03d}_FAILED"
                )
                blockers.extend(report.pass_blockers)
                break

            if cycle_number < cycle_count:
                sleep_function(float(interval_seconds))

    except KeyboardInterrupt:
        session_status = "INTERRUPTED"
        blockers.append("SESSION_INTERRUPTED")
    except Exception as exc:
        session_status = "FAILED"
        blockers.extend(
            (
                "SESSION_EXECUTION_EXCEPTION",
                f"SESSION_EXCEPTION_{type(exc).__name__.upper()}",
            )
        )

    completed_at = _utc(clock(), "completed_at")
    passed_count = sum(
        1 for report in reports if report.passed
    )
    failed_count = len(reports) - passed_count

    report = Task8LivePaperSessionReportV1(
        session_id=session_id,
        started_at=started_at,
        completed_at=completed_at,
        requested_cycle_count=cycle_count,
        completed_cycle_count=len(reports),
        passed_cycle_count=passed_count,
        failed_cycle_count=failed_count,
        total_nifty_evaluation_count=sum(
            item.nifty_evaluation_count
            for item in reports
        ),
        total_sensex_evaluation_count=sum(
            item.sensex_evaluation_count
            for item in reports
        ),
        interval_seconds=float(interval_seconds),
        session_status=session_status,
        branch=branch,
        commit=commit,
        cycle_run_ids=tuple(
            item.run_id for item in reports
        ),
        cycle_report_paths=tuple(
            str(path) for path in report_paths
        ),
        blockers=tuple(
            dict.fromkeys(
                str(item)
                for item in blockers
                if str(item)
            )
        ),
        paper_mode=all(
            item.paper_mode for item in reports
        )
        if reports
        else True,
        broker_submission_disabled=all(
            item.broker_submission_disabled
            for item in reports
        )
        if reports
        else True,
        live_execution_ineligible=all(
            item.live_execution_ineligible
            for item in reports
        )
        if reports
        else True,
    )

    session_path = destination / (
        f"{session_id}-session.json"
    )
    write_task8_session_report(
        report,
        session_path,
    )

    return report, session_path

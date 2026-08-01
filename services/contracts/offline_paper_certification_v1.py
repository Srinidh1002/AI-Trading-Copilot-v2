"""Typed deterministic Task 7 certification report contracts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar


_STATUSES = {"PASSED", "FAILED", "BLOCKED"}
_CATEGORIES = {
    "TWO_MARKET",
    "CAPITAL_RISK",
    "PAPER_LIFECYCLE",
    "RESTART_RECOVERY",
    "OPERATOR_DASHBOARD",
    "SAFETY_ISOLATION",
}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class OfflinePaperCertificationCheckV1:
    check_id: str
    category: str
    name: str
    status: str
    evidence: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("check_id", "name"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        category = _text(self.category, "category").upper()
        if category not in _CATEGORIES:
            raise ValueError("category")
        object.__setattr__(self, "category", category)

        status = _text(self.status, "status").upper()
        if status not in _STATUSES:
            raise ValueError("status")
        object.__setattr__(self, "status", status)

        for name in ("evidence", "blockers", "warnings"):
            object.__setattr__(
                self,
                name,
                _messages(getattr(self, name), name),
            )

        if not self.evidence:
            raise ValueError("evidence")
        if status == "PASSED" and self.blockers:
            raise ValueError("passed check cannot contain blockers")
        if status in {"FAILED", "BLOCKED"} and not self.blockers:
            raise ValueError("failed or blocked check requires blockers")


@dataclass(frozen=True, slots=True)
class OfflinePaperCertificationReportV1:
    SCHEMA_VERSION: ClassVar[str] = "offline_paper_certification_report.v1"

    report_id: str
    generated_at: datetime
    branch_name: str
    commit_sha: str
    checks: tuple[OfflinePaperCertificationCheckV1, ...]
    overall_status: str
    passed_count: int
    failed_count: int
    blocked_count: int
    execution_mode: str = "PAPER"
    network_access_used: bool = False
    broker_submission_enabled: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        for name in ("report_id", "branch_name", "commit_sha"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "generated_at",
            _aware(self.generated_at, "generated_at"),
        )

        if not isinstance(self.checks, tuple):
            raise TypeError("checks")
        if not self.checks:
            raise ValueError("checks")
        if any(
            type(check) is not OfflinePaperCertificationCheckV1
            for check in self.checks
        ):
            raise TypeError("checks")

        ids = tuple(check.check_id for check in self.checks)
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate check_id")

        expected_passed = sum(
            check.status == "PASSED" for check in self.checks
        )
        expected_failed = sum(
            check.status == "FAILED" for check in self.checks
        )
        expected_blocked = sum(
            check.status == "BLOCKED" for check in self.checks
        )

        counts = {
            "passed_count": (self.passed_count, expected_passed),
            "failed_count": (self.failed_count, expected_failed),
            "blocked_count": (self.blocked_count, expected_blocked),
        }
        for name, (actual, expected) in counts.items():
            if type(actual) is not int or actual < 0:
                raise ValueError(name)
            if actual != expected:
                raise ValueError(f"{name} mismatch")

        overall = _text(self.overall_status, "overall_status").upper()
        if expected_failed:
            expected_overall = "FAILED"
        elif expected_blocked:
            expected_overall = "BLOCKED"
        else:
            expected_overall = "PASSED"
        if overall != expected_overall:
            raise ValueError("overall_status")
        object.__setattr__(self, "overall_status", overall)

        if (
            self.execution_mode != "PAPER"
            or self.network_access_used is not False
            or self.broker_submission_enabled is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError("offline PAPER-only certification")

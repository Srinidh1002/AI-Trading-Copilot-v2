"""Immutable failure evidence for Task 8 PAPER canary execution."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from services.market_data_failure_evidence import (
    classify_market_data_exception,
)


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


def classify_task8_exception(
    exception: BaseException,
) -> tuple[bool, str]:
    """Return provider-throttle classification and sanitized reason."""

    return classify_market_data_exception(exception)


@dataclass(frozen=True, slots=True)
class Task8CanaryFailureReportV1:
    run_id: str
    requested_at: datetime
    completed_at: datetime
    status: str
    countable: bool
    completed_market_count: int
    provider_throttled: bool
    exception_type: str
    failure_reason: str
    paper_mode: bool
    broker_submission_enabled: bool
    live_execution_eligible: bool
    schema_version: str = (
        "task8_live_paper_canary_failure_report.v1"
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            _text(self.run_id, "run_id"),
        )
        object.__setattr__(
            self,
            "requested_at",
            _utc(self.requested_at, "requested_at"),
        )
        object.__setattr__(
            self,
            "completed_at",
            _utc(self.completed_at, "completed_at"),
        )
        object.__setattr__(
            self,
            "exception_type",
            _text(self.exception_type, "exception_type"),
        )
        object.__setattr__(
            self,
            "failure_reason",
            _text(self.failure_reason, "failure_reason"),
        )

        if self.requested_at > self.completed_at:
            raise ValueError(
                "requested_at must not exceed completed_at"
            )

        if self.status != "FAILED":
            raise ValueError("status")

        if self.countable is not False:
            raise ValueError("countable")

        if self.completed_market_count != 0:
            raise ValueError("completed_market_count")

        for name in (
            "provider_throttled",
            "paper_mode",
            "broker_submission_enabled",
            "live_execution_eligible",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        if (
            not self.paper_mode
            or self.broker_submission_enabled
            or self.live_execution_eligible
        ):
            raise ValueError(
                "failure evidence must remain PAPER-only"
            )

        if self.schema_version != (
            "task8_live_paper_canary_failure_report.v1"
        ):
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["requested_at"] = (
            self.requested_at.isoformat()
        )
        value["completed_at"] = (
            self.completed_at.isoformat()
        )
        return value

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def build_task8_canary_failure_report(
    *,
    run_id: str,
    requested_at: datetime,
    completed_at: datetime,
    exception: BaseException,
) -> Task8CanaryFailureReportV1:
    provider_throttled, failure_reason = (
        classify_task8_exception(exception)
    )

    return Task8CanaryFailureReportV1(
        run_id=run_id,
        requested_at=requested_at,
        completed_at=completed_at,
        status="FAILED",
        countable=False,
        completed_market_count=0,
        provider_throttled=provider_throttled,
        exception_type=type(exception).__name__,
        failure_reason=failure_reason,
        paper_mode=True,
        broker_submission_enabled=False,
        live_execution_eligible=False,
    )


def write_task8_canary_failure_report(
    report: Task8CanaryFailureReportV1,
    output_path: Path,
) -> Path:
    if type(report) is not Task8CanaryFailureReportV1:
        raise TypeError("report")

    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if path.exists():
        raise FileExistsError(
            f"immutable report path already exists: {path}"
        )

    path.write_text(
        report.to_json() + "\n",
        encoding="utf-8",
    )
    return path

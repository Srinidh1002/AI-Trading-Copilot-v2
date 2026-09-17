"""Typed replay acceptance output."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.contracts.final_decision_v1 import FinalDecisionV1


@dataclass(frozen=True, slots=True)
class ReplayExpectationMismatchV1:
    field: str
    expected: Any
    actual: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True, slots=True)
class ReplayAcceptanceResultV1:
    fixture_id: str
    fixture_name: str
    passed: bool
    decision: FinalDecisionV1 | None
    mismatches: tuple[ReplayExpectationMismatchV1, ...] = ()
    status: str = "PASS"
    error_detail: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {
            "PASS",
            "FAIL",
            "INSUFFICIENT_DATA",
            "ERROR",
        }:
            raise ValueError("Unsupported replay acceptance status.")

        if self.status == "PASS" and not self.passed:
            raise ValueError("PASS results must set passed=True.")

        if self.status != "PASS" and self.passed:
            raise ValueError("Non-PASS results must set passed=False.")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "fixture_id": self.fixture_id,
            "fixture_name": self.fixture_name,
            "passed": self.passed,
            "decision": (
                self.decision.to_dict()
                if self.decision is not None
                else None
            ),
            "mismatches": [
                mismatch.to_dict()
                for mismatch in self.mismatches
            ],
            "status": self.status,
            "error_detail": self.error_detail,
        }

        _assert_finite(payload)
        return payload

    def semantic_dict(self) -> dict[str, Any]:
        payload = self.to_dict()

        decision = payload.get("decision")
        if isinstance(decision, dict):
            decision.pop("decision_id", None)

        return payload


@dataclass(frozen=True, slots=True)
class ReplaySuiteResultV1:
    """Aggregate result for a deterministically ordered replay directory."""

    suite_id: str
    directory: str
    results: tuple[ReplayAcceptanceResultV1, ...]
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    schema_version: str = "replay_suite_result.v1"
    warnings: tuple[str, ...] = ()
    errors_detail: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != "replay_suite_result.v1":
            raise ValueError(
                "schema_version must be 'replay_suite_result.v1'."
            )

        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware.")

        unsupported = tuple(
            result.status
            for result in self.results
            if result.status
            not in {
                "PASS",
                "FAIL",
                "INSUFFICIENT_DATA",
                "ERROR",
            }
        )

        if unsupported:
            raise ValueError(
                "Replay suite contains an unsupported result status."
            )

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(
            result.status == "PASS"
            for result in self.results
        )

    @property
    def failed(self) -> int:
        return sum(
            result.status == "FAIL"
            for result in self.results
        )

    @property
    def insufficient_data(self) -> int:
        return sum(
            result.status == "INSUFFICIENT_DATA"
            for result in self.results
        )

    @property
    def errors(self) -> int:
        return sum(
            result.status == "ERROR"
            for result in self.results
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "suite_id": self.suite_id,
            "created_at": self.created_at.isoformat(),
            "directory": self.directory,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "insufficient_data": self.insufficient_data,
            "errors": self.errors,
            "results": [
                item.to_dict()
                for item in self.results
            ],
            "warnings": list(self.warnings),
            "errors_detail": list(self.errors_detail),
        }

        _assert_finite(payload)
        return payload

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "directory": self.directory,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "insufficient_data": self.insufficient_data,
            "errors": self.errors,
            "results": [
                item.semantic_dict()
                for item in self.results
            ],
            "warnings": list(self.warnings),
            "errors_detail": list(self.errors_detail),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def _assert_finite(value: Any) -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(
                "Replay suite results cannot serialize NaN or Infinity."
            )
        return

    if isinstance(value, dict):
        for item in value.values():
            _assert_finite(item)
        return

    if isinstance(value, (list, tuple)):
        for item in value:
            _assert_finite(item)
"""Immutable Task 9 startup-preflight phase and aggregate result contracts."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from services.contracts.task9_run_classification_v1 import validate_task9_run_classification
from services.contracts.task9_runtime_config_snapshot_v1 import (
    validate_task9_runtime_config_snapshot_reference,
)


class Task9StartupPreflightPhase(str, Enum):
    STATIC_CONFIG_VALIDATION = "STATIC_CONFIG_VALIDATION"
    PAPER_SAFETY = "PAPER_SAFETY"
    CAMPAIGN_RUN_ROOT_IDENTITY = "CAMPAIGN_RUN_ROOT_IDENTITY"
    PERSISTENCE_INTEGRITY_WRITABILITY = "PERSISTENCE_INTEGRITY_WRITABILITY"
    MARKET_SESSION_IDENTITY = "MARKET_SESSION_IDENTITY"
    ANGEL_CREDENTIALS_SESSION = "ANGEL_CREDENTIALS_SESSION"
    REQUIRED_ANGEL_CAPABILITY_READINESS = "REQUIRED_ANGEL_CAPABILITY_READINESS"
    OPTIONAL_PROVIDER_CAPABILITY_STATE = "OPTIONAL_PROVIDER_CAPABILITY_STATE"
    COLLECTOR_RUNTIME_READINESS = "COLLECTOR_RUNTIME_READINESS"
    DASHBOARD_ACTIVE_CAMPAIGN_AUTHORITY = "DASHBOARD_ACTIVE_CAMPAIGN_AUTHORITY"
    REPRODUCIBILITY_SNAPSHOT = "REPRODUCIBILITY_SNAPSHOT"
    FINAL_LAUNCH_APPROVAL = "FINAL_LAUNCH_APPROVAL"


class Task9StartupPreflightPhaseStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    BLOCKED_RETRYABLE = "BLOCKED_RETRYABLE"
    FAIL_FATAL = "FAIL_FATAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_RUN = "NOT_RUN"


_PHASES = tuple(Task9StartupPreflightPhase)
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_SECRET = re.compile(r"(?:secret|password|token|jwt|refresh|totp|authorization|api[_-]?key|client[_-]?id|\bpin\b)", re.IGNORECASE)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not (value := value.strip()):
        raise ValueError(name)
    if _SECRET.search(value):
        raise ValueError(f"{name} must not contain secret material")
    return value


def _reference(value: object, name: str) -> str:
    value = _text(value, name)
    if not _REFERENCE.fullmatch(value):
        raise ValueError(name)
    return value


def _aware_utc(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value.astimezone(timezone.utc)


def _freeze_metadata(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("metadata")
    frozen: dict[str, object] = {}
    for key, item in value.items():
        key = _reference(key, "metadata key")
        if type(item) not in {str, int, float, bool} and item is not None:
            raise ValueError("metadata")
        if isinstance(item, str):
            item = _text(item, "metadata value")
        frozen[key] = item
    try:
        json.dumps(frozen, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata") from exc
    return MappingProxyType(dict(sorted(frozen.items())))


@dataclass(frozen=True, slots=True)
class Task9StartupPreflightPhaseResultV1:
    phase: Task9StartupPreflightPhase
    status: Task9StartupPreflightPhaseStatus
    blocking: bool
    reason_code: str
    detail: str | None
    observed_at: datetime
    evidence_refs: tuple[str, ...] = ()
    incident_refs: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            phase = Task9StartupPreflightPhase(self.phase)
            status = Task9StartupPreflightPhaseStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise ValueError("phase/status") from exc
        if type(self.blocking) is not bool:
            raise TypeError("blocking")
        expected_blocking = status in {
            Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE,
            Task9StartupPreflightPhaseStatus.FAIL_FATAL,
        }
        if self.blocking != expected_blocking:
            raise ValueError("blocking")
        reason = _text(self.reason_code, "reason_code")
        if not _CODE.fullmatch(reason):
            raise ValueError("reason_code")
        detail = None if self.detail is None else _text(self.detail, "detail")
        if detail is not None and len(detail) > 512:
            raise ValueError("detail")
        if not isinstance(self.evidence_refs, tuple) or not isinstance(self.incident_refs, tuple):
            raise TypeError("references")
        evidence = tuple(_reference(item, "evidence_ref") for item in self.evidence_refs)
        incidents = tuple(_reference(item, "incident_ref") for item in self.incident_refs)
        if len(set(evidence)) != len(evidence) or len(set(incidents)) != len(incidents):
            raise ValueError("references")
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason_code", reason)
        object.__setattr__(self, "detail", detail)
        object.__setattr__(self, "observed_at", _aware_utc(self.observed_at, "observed_at"))
        object.__setattr__(self, "evidence_refs", evidence)
        object.__setattr__(self, "incident_refs", incidents)
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase.value, "status": self.status.value,
            "blocking": self.blocking, "reason_code": self.reason_code,
            "detail": self.detail, "observed_at": self.observed_at.isoformat(),
            "evidence_refs": list(self.evidence_refs), "incident_refs": list(self.incident_refs),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Task9StartupPreflightPhaseResultV1":
        if not isinstance(value, Mapping):
            raise TypeError("phase result")
        payload = dict(value)
        try:
            payload["observed_at"] = datetime.fromisoformat(payload["observed_at"])
            payload["evidence_refs"] = tuple(payload["evidence_refs"])
            payload["incident_refs"] = tuple(payload["incident_refs"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("phase result serialization") from exc
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class Task9StartupPreflightResultV1:
    preflight_id: str
    runtime_config_snapshot_id: str
    runtime_config_sha256: str
    campaign_id: str
    market_date: date
    official_run_id: str
    run_classification: str
    started_at: datetime
    completed_at: datetime
    phase_results: tuple[Task9StartupPreflightPhaseResultV1, ...]
    evidence_refs: tuple[str, ...] = ()
    schema_version: str = "task9_startup_preflight.v1"

    def __post_init__(self) -> None:
        if self.schema_version != "task9_startup_preflight.v1":
            raise ValueError("schema_version")
        for name in ("preflight_id", "campaign_id", "official_run_id"):
            object.__setattr__(self, name, _reference(getattr(self, name), name))
        snapshot_id, sha = validate_task9_runtime_config_snapshot_reference(
            self.runtime_config_snapshot_id, self.runtime_config_sha256,
        )
        object.__setattr__(self, "runtime_config_snapshot_id", snapshot_id)
        object.__setattr__(self, "runtime_config_sha256", sha)
        if type(self.market_date) is not date:
            raise ValueError("market_date")
        object.__setattr__(self, "run_classification", validate_task9_run_classification(self.run_classification))
        started = _aware_utc(self.started_at, "started_at")
        completed = _aware_utc(self.completed_at, "completed_at")
        if completed < started:
            raise ValueError("preflight timestamps")
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "completed_at", completed)
        if not isinstance(self.phase_results, tuple) or len(self.phase_results) != len(_PHASES):
            raise ValueError("phase_results")
        if any(type(item) is not Task9StartupPreflightPhaseResultV1 for item in self.phase_results):
            raise ValueError("phase_results")
        if tuple(item.phase for item in self.phase_results) != _PHASES:
            raise ValueError("phase order")
        seen_not_run = False
        for item in self.phase_results:
            if seen_not_run and item.status is not Task9StartupPreflightPhaseStatus.NOT_RUN:
                raise ValueError("phase after NOT_RUN")
            seen_not_run = seen_not_run or item.status is Task9StartupPreflightPhaseStatus.NOT_RUN
        if not isinstance(self.evidence_refs, tuple):
            raise TypeError("evidence_refs")
        refs = tuple(_reference(item, "evidence_ref") for item in self.evidence_refs)
        if len(set(refs)) != len(refs):
            raise ValueError("evidence_refs")
        object.__setattr__(self, "evidence_refs", refs)

    @property
    def overall_status(self) -> Task9StartupPreflightPhaseStatus:
        statuses = tuple(item.status for item in self.phase_results)
        if Task9StartupPreflightPhaseStatus.FAIL_FATAL in statuses:
            return Task9StartupPreflightPhaseStatus.FAIL_FATAL
        if Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE in statuses:
            return Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE
        final = self.phase_results[-1].status
        if final is not Task9StartupPreflightPhaseStatus.PASS:
            return final
        if Task9StartupPreflightPhaseStatus.NOT_RUN in statuses:
            return Task9StartupPreflightPhaseStatus.NOT_RUN
        return Task9StartupPreflightPhaseStatus.PASS

    @property
    def blocking_phase(self) -> Task9StartupPreflightPhase | None:
        for status in (Task9StartupPreflightPhaseStatus.FAIL_FATAL, Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE):
            for item in self.phase_results:
                if item.status is status:
                    return item.phase
        return None

    @property
    def launch_approved(self) -> bool:
        return (
            self.overall_status is Task9StartupPreflightPhaseStatus.PASS
            and self.phase_results[-1].status is Task9StartupPreflightPhaseStatus.PASS
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version, "preflight_id": self.preflight_id,
            "runtime_config_snapshot_id": self.runtime_config_snapshot_id,
            "runtime_config_sha256": self.runtime_config_sha256,
            "campaign_id": self.campaign_id, "market_date": self.market_date.isoformat(),
            "official_run_id": self.official_run_id, "run_classification": self.run_classification,
            "started_at": self.started_at.isoformat(), "completed_at": self.completed_at.isoformat(),
            "phase_results": [item.to_dict() for item in self.phase_results],
            "overall_status": self.overall_status.value, "launch_approved": self.launch_approved,
            "blocking_phase": None if self.blocking_phase is None else self.blocking_phase.value,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Task9StartupPreflightResultV1":
        if not isinstance(value, Mapping):
            raise TypeError("preflight")
        payload = dict(value)
        # Derived fields are serialized for reporting and must agree if present;
        # they are never accepted as caller authority.
        reported = {name: payload.pop(name, None) for name in (
            "overall_status", "launch_approved", "blocking_phase",
        )}
        try:
            payload["market_date"] = date.fromisoformat(payload["market_date"])
            payload["started_at"] = datetime.fromisoformat(payload["started_at"])
            payload["completed_at"] = datetime.fromisoformat(payload["completed_at"])
            payload["phase_results"] = tuple(Task9StartupPreflightPhaseResultV1.from_dict(item) for item in payload["phase_results"])
            payload["evidence_refs"] = tuple(payload["evidence_refs"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("preflight serialization") from exc
        result = cls(**payload)
        expected = {
            "overall_status": result.overall_status.value,
            "launch_approved": result.launch_approved,
            "blocking_phase": None if result.blocking_phase is None else result.blocking_phase.value,
        }
        if any(reported[name] is not None and reported[name] != expected[name] for name in expected):
            raise ValueError("derived preflight result")
        return result

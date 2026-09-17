"""Immutable, deterministic structured audit event contract."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

EVENT_TYPES = frozenset({
    "SNAPSHOT_RECEIVED", "SNAPSHOT_VALIDATED", "ANALYSIS_STARTED", "ANALYSIS_COMPLETED", "ANALYSIS_FAILED",
    "DECISION_STARTED", "DECISION_COMPLETED", "DECISION_BLOCKED", "DECISION_FAILED",
    "DASHBOARD_ANALYSIS_STARTED", "DASHBOARD_ANALYSIS_COMPLETED", "DASHBOARD_ANALYSIS_FAILED",
    "CLI_ANALYSIS_STARTED", "CLI_ANALYSIS_COMPLETED", "CLI_ANALYSIS_FAILED",
    "PAPER_PREPARATION_STARTED", "PAPER_PREPARATION_COMPLETED", "PAPER_PREPARATION_REJECTED",
    "PAPER_PREPARATION_BLOCKED", "PAPER_PREPARATION_FAILED",
    "PAPER_EXECUTION_REQUESTED", "PAPER_EXECUTION_REJECTED", "PAPER_EXECUTION_SUBMITTED", "PAPER_EXECUTION_FAILED",
    "REPLAY_STARTED", "REPLAY_COMPLETED", "REPLAY_FAILED", "REPLAY_SUITE_STARTED", "REPLAY_SUITE_COMPLETED",
    "REPLAY_FIXTURE_ERROR", "COMPARISON_COMPLETED", "COMPARISON_FAILED",
    "SESSION_VALIDATION_STARTED", "SESSION_VALIDATION_COMPLETED", "SESSION_VALIDATION_BLOCKED", "SESSION_VALIDATION_FAILED",
    "OPTION_SELECTION_STARTED", "OPTION_SELECTION_COMPLETED", "OPTION_SELECTION_BLOCKED", "OPTION_SELECTION_FAILED",
    "TRADE_PLAN_STARTED", "TRADE_PLAN_COMPLETED", "TRADE_PLAN_BLOCKED", "TRADE_PLAN_FAILED",
    "POSITION_SIZING_STARTED", "POSITION_SIZING_COMPLETED", "POSITION_SIZING_BLOCKED", "POSITION_SIZING_FAILED",
    "RISK_VALIDATION_STARTED", "RISK_VALIDATION_COMPLETED", "RISK_VALIDATION_BLOCKED", "RISK_VALIDATION_FAILED",
})
SEVERITIES = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
OUTCOMES = frozenset({"STARTED", "SUCCEEDED", "BLOCKED", "REJECTED", "FAILED", "SKIPPED", "INSUFFICIENT_DATA"})


@dataclass(frozen=True, slots=True)
class AuditEventV1:
    event_id: str
    event_type: str
    event_name: str
    occurred_at: datetime
    severity: str
    outcome: str
    component: str
    operation: str
    schema_version: str = "audit_event.v1"
    trace_id: str | None = None
    correlation_id: str | None = None
    parent_event_id: str | None = None
    snapshot_id: str | None = None
    analysis_id: str | None = None
    decision_id: str | None = None
    candidate_id: str | None = None
    replay_id: str | None = None
    fixture_id: str | None = None
    suite_id: str | None = None
    symbol: str | None = None
    exchange: str | None = None
    action: str | None = None
    authorization_status: str | None = None
    execution_status: str | None = None
    duration_ms: float | None = None
    message: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != "audit_event.v1" or not self.event_id or not self.event_name or not self.component or not self.operation:
            raise ValueError("Audit event identity and schema are required.")
        if self.event_type not in EVENT_TYPES or self.severity not in SEVERITIES or self.outcome not in OUTCOMES:
            raise ValueError("Audit event uses unsupported controlled vocabulary.")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware.")
        if self.duration_ms is not None and (self.duration_ms < 0 or not math.isfinite(self.duration_ms)):
            raise ValueError("duration_ms must be finite and non-negative.")
        object.__setattr__(self, "attributes", dict(self.attributes))
        _finite(self.attributes)

    def to_dict(self) -> dict[str, Any]:
        values = {name: getattr(self, name) for name in self.__dataclass_fields__}
        values["occurred_at"] = self.occurred_at.isoformat()
        values["attributes"] = dict(sorted(self.attributes.items()))
        values["warnings"] = list(self.warnings)
        values["errors"] = list(self.errors)
        return values

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def semantic_dict(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("event_id"); value.pop("occurred_at")
        return value


def _finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Audit attributes cannot contain NaN or Infinity.")
    if isinstance(value, Mapping):
        for item in value.values(): _finite(item)
    elif isinstance(value, (tuple, list)):
        for item in value: _finite(item)

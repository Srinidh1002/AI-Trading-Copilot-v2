"""One-shot, parent-only acceptance runner for Task 1C shared INDIA_VIX reads."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.contracts.certified_shared_market_context_v1 import CertifiedSharedMarketContextV1
from services.contracts.two_market_decision_result_v1 import TwoMarketDecisionResultV1


def _utc(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value.astimezone(timezone.utc)


def _safe_messages(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError("messages")
    return tuple(str(item) for item in value if str(item))


@dataclass(frozen=True, slots=True)
class Task1CParentOnlyExecutionV1:
    decision: TwoMarketDecisionResultV1
    shared_context: CertifiedSharedMarketContextV1
    call_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        if type(self.decision) is not TwoMarketDecisionResultV1 or type(self.shared_context) is not CertifiedSharedMarketContextV1:
            raise TypeError("typed parent evidence is required")
        if self.shared_context.india_vix_capture is None:
            raise ValueError("INDIA_VIX_CAPTURE_MISSING")
        counts = {str(key): value for key, value in self.call_counts.items()}
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise ValueError("call_counts")
        object.__setattr__(self, "call_counts", counts)


@dataclass(frozen=True, slots=True)
class Task1CParentOnlyDependenciesV1:
    """Deliberately has no planner, lifecycle, monitoring, or order capability."""
    branch: str
    commit: str
    run_parent: Callable[[], Task1CParentOnlyExecutionV1]
    clock: Callable[[], datetime]
    id_factory: Callable[[], str]
    last_substage: Callable[[], str] = lambda: "DEPENDENCY_READY"
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        if not callable(self.run_parent) or not callable(self.clock) or not callable(self.id_factory) or not callable(self.last_substage):
            raise TypeError("parent-only dependencies require callables")
        if self.execution_mode != "PAPER" or self.live_execution_eligible or self.broker_order_submission:
            raise ValueError("Task 1C parent-only runner is PAPER-only")


@dataclass(frozen=True, slots=True)
class Task1CParentOnlyReportV1:
    run_id: str; cycle_id: str; started_at: datetime; completed_at: datetime
    execution_mode: str; live_execution_eligible: bool; broker_order_submission: bool
    parent_action: str; selected_market: str; parent_status: str
    parent_blockers: tuple[str, ...]; parent_warnings: tuple[str, ...]
    nifty: Mapping[str, Any]; sensex: Mapping[str, Any]; india_vix: Mapping[str, Any]
    call_counts: Mapping[str, int]
    schema_version: str = "task1c_parent_only_live_canary_report.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "started_at", _utc(self.started_at, "started_at")); object.__setattr__(self, "completed_at", _utc(self.completed_at, "completed_at"))
        if self.started_at > self.completed_at or self.execution_mode != "PAPER" or self.live_execution_eligible or self.broker_order_submission:
            raise ValueError("parent-only safety")
        if self.schema_version != "task1c_parent_only_live_canary_report.v1": raise ValueError("schema_version")
        for name in ("planner_invocations", "lifecycle_invocations", "monitoring_mutations", "broker_order_invocations"):
            if self.call_counts.get(name) != 0: raise ValueError(f"{name} must remain zero")
        object.__setattr__(self, "parent_blockers", _safe_messages(self.parent_blockers)); object.__setattr__(self, "parent_warnings", _safe_messages(self.parent_warnings))

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self); value["started_at"] = self.started_at.isoformat(); value["completed_at"] = self.completed_at.isoformat()
        value["parent_blockers"] = list(self.parent_blockers); value["parent_warnings"] = list(self.parent_warnings)
        return value

    def to_json(self) -> str: return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _market(entry, broader) -> dict[str, Any]:
    candidate = entry.child.candidate
    regime = candidate.regime if candidate else None
    return {"terminal_status": entry.child.terminal_status, "candidate_available": candidate is not None,
            "action": candidate.direction if candidate else "UNAVAILABLE", "regime_status": getattr(regime, "context_status", "UNAVAILABLE"),
            "regime_suitability": getattr(regime, "entry_suitability", "UNAVAILABLE"),
            "broader_status": getattr(broader, "intelligence_status", "UNAVAILABLE"), "broader_blockers": list(getattr(broader, "blockers", ())),
            "broader_warnings": list(getattr(broader, "warnings", ())), "external_warnings": list(getattr(getattr(candidate, "external_context", None), "warnings", ())) if candidate else []}


def run_task1c_parent_only_live_canary(dependencies: Task1CParentOnlyDependenciesV1) -> Task1CParentOnlyReportV1:
    if type(dependencies) is not Task1CParentOnlyDependenciesV1: raise TypeError("dependencies")
    started = _utc(dependencies.clock(), "clock")
    execution = dependencies.run_parent()
    if type(execution) is not Task1CParentOnlyExecutionV1: raise TypeError("run_parent must return exact Task1CParentOnlyExecutionV1")
    decision, context, capture = execution.decision, execution.shared_context, execution.shared_context.india_vix_capture
    if capture.source_status != "READY": raise RuntimeError("INDIA_VIX_CAPTURE_NOT_READY")
    nifty_snapshot, sensex_snapshot = (getattr(context.nifty_broader_market, "volatility_context", None), getattr(context.sensex_broader_market, "volatility_context", None))
    snapshot_ids = context.cache_metadata.get("india_vix_normalization", {})
    counts = dict(execution.call_counts)
    counts.update({"planner_invocations": 0, "lifecycle_invocations": 0, "monitoring_mutations": 0, "broker_order_invocations": 0})
    if counts.get("india_vix_master_resolution_count") != 1 or counts.get("india_vix_quote_count") != 1 or counts.get("india_vix_normalization_count") != 1:
        raise RuntimeError("INDIA_VIX_CALL_COUNT_INVALID")
    entries = {entry.child.underlying_symbol: entry for entry in decision.entries}
    return Task1CParentOnlyReportV1(
        run_id=dependencies.id_factory(), cycle_id=decision.parent_cycle_id, started_at=started, completed_at=_utc(dependencies.clock(), "clock"),
        execution_mode="PAPER", live_execution_eligible=False, broker_order_submission=False, parent_action=decision.decision,
        selected_market=decision.selected_market[0] if decision.selected_market else "NONE", parent_status="COMPLETED",
        parent_blockers=decision.blockers, parent_warnings=decision.warnings,
        nifty=_market(entries["NIFTY"], context.nifty_broader_market), sensex=_market(entries["SENSEX"], context.sensex_broader_market),
        india_vix={"capture_status": capture.source_status, "current_value": capture.current_value, "previous_close": capture.previous_close,
                   "regime": getattr(nifty_snapshot, "volatility_regime", "UNAVAILABLE"),
                   "provider_timestamp": capture.provider_timestamp.isoformat() if capture.provider_timestamp else None, "evaluated_timestamp": capture.evaluated_at.isoformat(),
                   "freshness_age_seconds": (capture.evaluated_at-capture.provider_timestamp).total_seconds() if capture.provider_timestamp else None,
                   "source_provider_id": capture.provider, "provider_symbol": capture.provider_symbol, "provider_exchange": capture.provider_exchange,
                   "instrument_type": capture.instrument_type, "instrument_token": capture.provider_token, "blockers": list(capture.blockers), "warnings": list(capture.warnings),
                   "shared_capture_id": capture.capture_id, "nifty_snapshot_id": snapshot_ids.get("nifty_snapshot_id"), "sensex_snapshot_id": snapshot_ids.get("sensex_snapshot_id"), "same_observation_reused": True},
        call_counts=counts,
    )


def write_task1c_parent_only_report(report: Task1CParentOnlyReportV1, output_path: Path) -> Path:
    path = Path(output_path)
    if path.exists(): raise FileExistsError("immutable report path already exists")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(report.to_json() + "\n", encoding="utf-8")
    return path

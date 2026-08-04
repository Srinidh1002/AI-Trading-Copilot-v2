"""Task 8 live-read PAPER certification seam.

This module deliberately owns certification evidence only.  It delegates
market comparison to the certified two-market runtime and delegates planning
to the existing P6/P7/P8 executor supplied by the composition.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionResultV1,
)


Clock = Callable[[], datetime]
IdFactory = Callable[[], str]
Preflight = Callable[[], Mapping[str, object]]
ParentCycle = Callable[[], TwoMarketDecisionResultV1]
SelectedPlanner = Callable[[tuple[str, str]], PaperOrchestrationCycleResultV1]
Monitoring = Callable[[], PaperOrchestrationCycleResultV1 | None]


def _utc(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value.astimezone(timezone.utc)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name)
    return value.strip()


@dataclass(frozen=True, slots=True)
class Task8CanaryReportV1:
    run_id: str
    generated_at: datetime
    branch: str
    commit: str
    outer_status: str
    nifty_evaluation_count: int
    nifty_terminal_status: str
    sensex_evaluation_count: int
    sensex_terminal_status: str
    freshness_status: str
    timestamp_skew_status: str
    selected_market: str
    rejected_market: str | None
    rejection_reasons: tuple[str, ...]
    final_action: str
    planning_status: str
    lifecycle_status: str
    monitoring_status: str
    persistence_status: str
    journal_status: str
    paper_mode: bool
    network_live_read_usage: bool
    broker_submission_disabled: bool
    live_execution_ineligible: bool
    pass_blockers: tuple[str, ...]
    schema_version: str = "task8_live_paper_canary_report.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(self, "branch", _text(self.branch, "branch"))
        object.__setattr__(self, "commit", _text(self.commit, "commit"))
        object.__setattr__(self, "generated_at", _utc(self.generated_at, "generated_at"))
        if self.schema_version != "task8_live_paper_canary_report.v1":
            raise ValueError("schema_version")
        if self.selected_market not in {"NIFTY", "SENSEX", "NONE"}:
            raise ValueError("selected_market")
        if self.nifty_evaluation_count != 1 or self.sensex_evaluation_count != 1:
            raise ValueError("exactly one evaluation per market is required")
        if not all(type(value) is bool for value in (self.paper_mode, self.network_live_read_usage, self.broker_submission_disabled, self.live_execution_ineligible)):
            raise TypeError("safety flags")
        if not isinstance(self.pass_blockers, tuple) or not isinstance(self.rejection_reasons, tuple):
            raise TypeError("report messages")

    @property
    def passed(self) -> bool:
        return self.outer_status == "PASSED" and not self.pass_blockers

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["generated_at"] = self.generated_at.isoformat()
        value["rejection_reasons"] = list(self.rejection_reasons)
        value["pass_blockers"] = list(self.pass_blockers)
        return value

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class Task8CanaryDependenciesV1:
    """Injected integration boundary; keeps tests deterministic and credentials out."""

    branch: str
    commit: str
    preflight: Preflight
    parent_cycle: ParentCycle
    selected_planner: SelectedPlanner
    monitoring: Monitoring
    clock: Clock
    id_factory: IdFactory
    network_live_read_usage: bool = True
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("preflight", "parent_cycle", "selected_planner", "monitoring", "clock", "id_factory"):
            if not callable(getattr(self, name)):
                raise TypeError(name)
        if self.execution_mode != "PAPER" or self.live_execution_eligible or self.broker_order_submission:
            raise ValueError("Task 8 canary is PAPER-only with broker submission disabled")


def _stage_status(result: PaperOrchestrationCycleResultV1 | None, stage: str) -> str:
    if result is None:
        return "NOT_RUN"
    for item in result.stage_results:
        if item.stage == stage:
            return item.status
    return "NOT_RUN"


def _cycle_inner_blockers(result: PaperOrchestrationCycleResultV1 | None) -> tuple[str, ...]:
    if result is None:
        return ()
    failures = list(result.blockers) + list(result.errors)
    for stage in result.stage_results:
        if stage.status == "FAILED":
            failures.append(f"{stage.stage}_FAILED")
        failures.extend(stage.blockers)
        failures.extend(stage.errors)
    return tuple(dict.fromkeys(str(item) for item in failures if str(item)))


def run_task8_live_paper_canary(dependencies: Task8CanaryDependenciesV1) -> Task8CanaryReportV1:
    """Execute exactly one parent comparison and selected-only planning.

    A ``NO_TRADE`` parent decision is a successful certification outcome when
    every safety, freshness and inner-result gate is evidenced.
    """
    if type(dependencies) is not Task8CanaryDependenciesV1:
        raise TypeError("dependencies")
    preflight = dict(dependencies.preflight())
    blockers = list(str(item) for item in preflight.get("blockers", ()) if str(item))
    # A closed market is an expected valid NO_TRADE condition.  The preflight
    # must prove that session status was checked, not demand that it is open.
    required = ("branch_worktree", "paper_mode", "live_execution_ineligible", "broker_submission_disabled", "nifty_provider", "sensex_provider", "routing", "persistence_writable", "journal_writable", "emergency_halt", "market_session_checked", "credentials_present")
    blockers.extend(f"PREFLIGHT_{key.upper()}" for key in required if preflight.get(key) is not True)

    decision = dependencies.parent_cycle()
    if type(decision) is not TwoMarketDecisionResultV1:
        raise TypeError("parent_cycle must return TwoMarketDecisionResultV1")
    nifty, sensex = decision.entries
    freshness_ok = all(entry.child.terminal_status == "COMPLETED" and entry.child.candidate is not None and entry.child.candidate.market_timestamp <= decision.completed_at for entry in decision.entries)
    skew_ok = not any(entry.outcome_reason == "SKEW_BLOCKED" for entry in decision.entries)
    if not freshness_ok:
        blockers.append("FRESHNESS_EVIDENCE_FAILED")
    if not skew_ok:
        blockers.append("TIMESTAMP_SKEW_FAILED")

    selected = decision.selected_market
    planned: PaperOrchestrationCycleResultV1 | None = None
    if selected is not None:
        planned = dependencies.selected_planner(selected)
        if type(planned) is not PaperOrchestrationCycleResultV1:
            raise TypeError("selected_planner must return PaperOrchestrationCycleResultV1")
        for stage in ("P6_PLAN", "P7_LIFECYCLE", "PERSISTENCE"):
            if _stage_status(planned, stage) == "NOT_RUN":
                blockers.append(f"{stage}_EVIDENCE_UNAVAILABLE")
    monitoring = dependencies.monitoring()
    if monitoring is not None and type(monitoring) is not PaperOrchestrationCycleResultV1:
        raise TypeError("monitoring must return PaperOrchestrationCycleResultV1 or None")
    blockers.extend(_cycle_inner_blockers(planned))
    blockers.extend(_cycle_inner_blockers(monitoring))
    if planned is not None and any(action not in {"OPEN_POSITION"} for action in planned.paper_actions):
        blockers.append("UNSUPPORTED_PAPER_ACTION")

    rejected = None
    reasons: tuple[str, ...] = ()
    if selected is not None:
        loser = sensex if selected[0] == "NIFTY" else nifty
        rejected, reasons = loser.child.underlying_symbol, (loser.outcome_reason, *loser.rationale)
    elif decision.decision != "NO_TRADE":
        blockers.append("UNSUPPORTED_PARENT_DECISION")

    unique_blockers = tuple(dict.fromkeys(blockers))
    return Task8CanaryReportV1(
        run_id=dependencies.id_factory(), generated_at=dependencies.clock(), branch=dependencies.branch, commit=dependencies.commit,
        outer_status="PASSED" if not unique_blockers else "FAILED",
        nifty_evaluation_count=1, nifty_terminal_status=nifty.child.terminal_status,
        sensex_evaluation_count=1, sensex_terminal_status=sensex.child.terminal_status,
        freshness_status="PASSED" if freshness_ok else "FAILED", timestamp_skew_status="PASSED" if skew_ok else "FAILED",
        selected_market=selected[0] if selected else "NONE", rejected_market=rejected, rejection_reasons=reasons,
        final_action="NO_TRADE" if selected is None else (planned.cycle_status if planned else "PLANNING_NOT_RUN"),
        planning_status=planned.cycle_status if planned else "NOT_RUN", lifecycle_status=_stage_status(planned, "P7_LIFECYCLE"),
        monitoring_status=monitoring.cycle_status if monitoring else "NOT_RUN", persistence_status=_stage_status(planned, "PERSISTENCE"),
        journal_status=str(preflight.get("journal_status", "UNKNOWN")), paper_mode=dependencies.execution_mode == "PAPER",
        network_live_read_usage=dependencies.network_live_read_usage, broker_submission_disabled=not dependencies.broker_order_submission,
        live_execution_ineligible=not dependencies.live_execution_eligible, pass_blockers=unique_blockers,
    )


def write_task8_report(report: Task8CanaryReportV1, output_path: Path) -> Path:
    if type(report) is not Task8CanaryReportV1:
        raise TypeError("report")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"immutable report path already exists: {path}")
    path.write_text(report.to_json() + "\n", encoding="utf-8")
    return path

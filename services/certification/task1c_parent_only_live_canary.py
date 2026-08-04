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
    nifty: Mapping[str, Any]; sensex: Mapping[str, Any]; india_vix: Mapping[str, Any]; external_context: Mapping[str, Any]
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


def _component_status(entry, broader, external) -> dict[str, Any]:
    candidate = entry.child.candidate
    regime = candidate.regime if candidate else None
    external_component = getattr(regime, "external_context_regime_component", None)
    components = {
        "session": getattr(getattr(candidate, "session", None), "validation_status", "UNAVAILABLE"),
        "freshness": getattr(getattr(candidate, "freshness", None), "quality_status", "UNAVAILABLE"),
        "data_quality": getattr(getattr(candidate, "data_quality", None), "quality_status", "UNAVAILABLE"),
        "technical": getattr(getattr(candidate, "technical", None), "intelligence_status", "UNAVAILABLE"),
        "multi_timeframe": getattr(getattr(candidate, "multi_timeframe", None), "snapshot_status", "UNAVAILABLE"),
        "option_chain": getattr(getattr(candidate, "option_chain", None), "intelligence_status", "UNAVAILABLE"),
        "ranking": getattr(getattr(candidate, "option_contract_eligibility", None), "ranking_status", "UNAVAILABLE"),
        "broader_context": getattr(broader, "intelligence_status", "UNAVAILABLE"),
        "external_context": getattr(external_component, "context_status", getattr(external, "context_status", "UNAVAILABLE")),
        "market_regime": getattr(regime, "context_status", "UNAVAILABLE"),
    }
    if candidate is None:
        components.update({name: "NOT_EVALUATED" for name in ("freshness", "data_quality", "session", "technical", "multi_timeframe", "option_chain", "ranking", "market_regime")})
        components["candidate_composition"] = "FAILED" if entry.child.terminal_status == "FAILED" else "UNAVAILABLE"
    terminal_reason_codes = tuple(dict.fromkeys(tuple(getattr(candidate, "blockers", ())) + tuple(getattr(regime, "blockers", ())) + tuple(getattr(broader, "blockers", ()) if candidate else ()) + tuple(entry.child.blockers) + tuple(entry.child.errors)))
    terminal_components = {
        code.removeprefix("EVIDENCE_UNAVAILABLE_").lower()
        for code in terminal_reason_codes if code.startswith("EVIDENCE_UNAVAILABLE_")
    }
    terminal_components.update(
        code.removeprefix("REQUIRED_").removesuffix("_UNUSABLE").lower()
        for code in terminal_reason_codes if code.startswith("REQUIRED_") and code.endswith("_UNUSABLE")
    )
    terminal_components = tuple(sorted(terminal_components))
    terminal_components = tuple("broader_context" if item == "broader_market" else item for item in terminal_components)
    if broader is not None and getattr(broader, "intelligence_status", "UNAVAILABLE") in {"BLOCKED", "STALE", "INSUFFICIENT_DATA", "UNAVAILABLE"} and getattr(broader, "blockers", ()):
        terminal_components = tuple(sorted(set((*terminal_components, "broader_context"))))
    if entry.child.terminal_status == "FAILED" and "CANDIDATE_COMPOSITION_FAILED" in terminal_reason_codes:
        terminal_components = tuple(sorted(set((*terminal_components, "candidate_composition"))))
    if "SPOT_EVIDENCE_UNAVAILABLE" in terminal_reason_codes:
        terminal_components = tuple(sorted(set((*terminal_components, "spot"))))
    if "SESSION_EVIDENCE_UNAVAILABLE" in terminal_reason_codes:
        terminal_components = tuple(sorted(set((*terminal_components, "session"))))
    if not terminal_components and getattr(regime, "context_status", "UNAVAILABLE") == "BLOCKED":
        terminal_components = ("market_regime",)
    return {"statuses": components, "terminal_components": list(terminal_components), "terminal_reason_codes": list(terminal_reason_codes)}


def _candle_diagnostics(context, symbol, exchange, broader) -> dict[str, Any]:
    series = (context.nifty_candle_series if (symbol, exchange) == ("NIFTY", "NSE") else context.sensex_candle_series).get("5m")
    completed = tuple(item for item in series.candles if item.is_complete) if series else ()
    final = completed[-1] if completed else None
    capture = context.cache_metadata.get("capture_diagnostics", {}).get(symbol, {})
    evidence = broader.cross_market_evidence[0] if broader and broader.cross_market_evidence else None
    skew = abs((evidence.primary_source_timestamp - evidence.related_source_timestamp).total_seconds()) if evidence else None
    candles = capture.get("cache_metadata", {}).get("candles", {}).get("5m", {}) if isinstance(capture, Mapping) else {}
    return {"timeframe": "5m", "candle_source_timestamp": final.end_at.isoformat() if final else None, "final_completed_candle_timestamp": final.end_at.isoformat() if final else None, "provider_timestamp": capture.get("provider_timestamp").isoformat() if capture.get("provider_timestamp") else None, "received_at": capture.get("received_at").isoformat() if capture.get("received_at") else None, "evaluated_at": context.evaluated_at.isoformat(), "candle_count": len(completed), "cache_status": candles.get("cache_status", "UNKNOWN") if isinstance(candles, Mapping) else "UNKNOWN", "source_age_seconds": (context.evaluated_at - final.end_at).total_seconds() if final else None, "cross_market_skew_seconds": skew, "shared_candle_cutoff": capture.get("shared_candle_cutoff").isoformat() if capture.get("shared_candle_cutoff") else None}


def _market(entry, broader, external, context) -> dict[str, Any]:
    candidate = entry.child.candidate
    regime = candidate.regime if candidate else None
    external_component = getattr(regime, "external_context_regime_component", None)
    return {"terminal_status": entry.child.terminal_status, "candidate_available": candidate is not None,
            "action": candidate.direction if candidate else "UNAVAILABLE", "regime_status": getattr(regime, "context_status", "UNAVAILABLE"),
            "regime_suitability": getattr(regime, "entry_suitability", "UNAVAILABLE"),
            "broader_status": getattr(broader, "intelligence_status", "UNAVAILABLE"), "broader_blockers": list(getattr(broader, "blockers", ())),
            "broader_warnings": list(getattr(broader, "warnings", ())),
            "external_status": getattr(external_component, "context_status", getattr(external, "context_status", "UNAVAILABLE")),
            "external_availability": getattr(external_component, "context_status", "UNAVAILABLE") not in {"UNAVAILABLE", "BLOCKED"},
            "external_blockers": list(getattr(external_component, "blockers", getattr(external, "blockers", ()))),
            "external_warnings": list(getattr(external_component, "warnings", getattr(external, "warnings", ()))),
            "external_direction": getattr(external_component, "directional_state", None),
            "component_summary": _component_status(entry, broader, external),
            "candle_timestamp_diagnostics": _candle_diagnostics(context, entry.child.underlying_symbol, entry.child.exchange, broader)}


def run_task1c_parent_only_live_canary(dependencies: Task1CParentOnlyDependenciesV1) -> Task1CParentOnlyReportV1:
    if type(dependencies) is not Task1CParentOnlyDependenciesV1: raise TypeError("dependencies")
    started = _utc(dependencies.clock(), "clock")
    execution = dependencies.run_parent()
    if type(execution) is not Task1CParentOnlyExecutionV1: raise TypeError("run_parent must return exact Task1CParentOnlyExecutionV1")
    decision, context, capture = execution.decision, execution.shared_context, execution.shared_context.india_vix_capture
    if capture.source_status != "READY": raise RuntimeError("INDIA_VIX_CAPTURE_NOT_READY")
    nifty_snapshot, sensex_snapshot = (getattr(context.nifty_broader_market, "volatility_context", None), getattr(context.sensex_broader_market, "volatility_context", None))
    snapshot_ids = context.cache_metadata.get("india_vix_normalization", {})
    external = context.shared_external_context
    counts = dict(execution.call_counts)
    counts.update({"planner_invocations": 0, "lifecycle_invocations": 0, "monitoring_mutations": 0, "broker_order_invocations": 0})
    if external is not None: counts.update({"external_context_build_count": external.build_count, "external_regime_component_evaluation_count": 2, "global_provider_call_count": 0, "institutional_provider_call_count": 0, "event_provider_call_count": 0, "breadth_provider_call_count": 0})
    if counts.get("india_vix_master_resolution_count") != 1 or counts.get("india_vix_quote_count") != 1 or counts.get("india_vix_normalization_count") != 1:
        raise RuntimeError("INDIA_VIX_CALL_COUNT_INVALID")
    entries = {entry.child.underlying_symbol: entry for entry in decision.entries}
    return Task1CParentOnlyReportV1(
        run_id=dependencies.id_factory(), cycle_id=decision.parent_cycle_id, started_at=started, completed_at=_utc(dependencies.clock(), "clock"),
        execution_mode="PAPER", live_execution_eligible=False, broker_order_submission=False, parent_action=decision.decision,
        selected_market=decision.selected_market[0] if decision.selected_market else "NONE", parent_status="COMPLETED",
        parent_blockers=decision.blockers, parent_warnings=decision.warnings,
        nifty=_market(entries["NIFTY"], context.nifty_broader_market, external.for_market("NIFTY", "NSE") if external else None, context), sensex=_market(entries["SENSEX"], context.sensex_broader_market, external.for_market("SENSEX", "BSE") if external else None, context),
        india_vix={"capture_status": capture.source_status, "current_value": capture.current_value, "previous_close": capture.previous_close,
                   "regime": getattr(nifty_snapshot, "volatility_regime", "UNAVAILABLE"),
                   "provider_timestamp": capture.provider_timestamp.isoformat() if capture.provider_timestamp else None, "evaluated_timestamp": capture.evaluated_at.isoformat(),
                   "freshness_age_seconds": (capture.evaluated_at-capture.provider_timestamp).total_seconds() if capture.provider_timestamp else None,
                   "source_provider_id": capture.provider, "provider_symbol": capture.provider_symbol, "provider_exchange": capture.provider_exchange,
                   "instrument_type": capture.instrument_type, "instrument_token": capture.provider_token, "blockers": list(capture.blockers), "warnings": list(capture.warnings),
                   "shared_capture_id": capture.capture_id, "nifty_snapshot_id": snapshot_ids.get("nifty_snapshot_id"), "sensex_snapshot_id": snapshot_ids.get("sensex_snapshot_id"), "same_observation_reused": True},
        external_context={"external_context_build_count": external.build_count if external else 0, "shared_context_id": external.cycle_id if external else None, "evaluated_at": external.evaluated_at.isoformat() if external else None, "same_shared_input_reused_by_both_markets": external is not None, "provider_call_counts": {"global": 0, "institutional": 0, "event": 0, "breadth": 0}, "nifty": {"result_id": external.nifty.external_market_context_result_id, "aggregate_status": external.nifty.context_status, "availability": external.nifty.context_status not in {"UNAVAILABLE", "BLOCKED"}, "blockers": list(external.nifty.blockers), "warnings": list(external.nifty.warnings), "global_status": external.nifty.global_context.context_status, "institutional_status": external.nifty.institutional_context.context_status, "event_status": external.nifty.event_context.context_status} if external else None, "sensex": {"result_id": external.sensex.external_market_context_result_id, "aggregate_status": external.sensex.context_status, "availability": external.sensex.context_status not in {"UNAVAILABLE", "BLOCKED"}, "blockers": list(external.sensex.blockers), "warnings": list(external.sensex.warnings), "global_status": external.sensex.global_context.context_status, "institutional_status": external.sensex.institutional_context.context_status, "event_status": external.sensex.event_context.context_status} if external else None},
        call_counts=counts,
    )


def write_task1c_parent_only_report(report: Task1CParentOnlyReportV1, output_path: Path) -> Path:
    path = Path(output_path)
    if path.exists(): raise FileExistsError("immutable report path already exists")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(report.to_json() + "\n", encoding="utf-8")
    return path

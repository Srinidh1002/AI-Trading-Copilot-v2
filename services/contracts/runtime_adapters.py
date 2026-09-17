"""Optional, side-effect-free shadow representations for legacy runtime paths.

Nothing in this module is wired into a production entry point.  Callers may
invoke it for diagnostics; failures are contained in its result mapping.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Mapping

from .final_decision_v1 import (
    AuthorizationStatus, FinalDecisionV1, from_live_option_pipeline_response,
    from_trade_engine_response,
)
from .market_snapshot_v1 import (
    MarketSnapshotV1, SnapshotValidationError, from_dashboard_snapshot,
    from_live_analysis_inputs,
)


def _result(snapshot: MarketSnapshotV1 | None, decision: FinalDecisionV1 | None, warnings: list[str], errors: list[str]) -> dict[str, Any]:
    valid = bool(snapshot and decision and snapshot.validation_passed and decision.validation_passed and not errors)
    return {"snapshot_v1": snapshot, "decision_v1": decision, "valid": valid, "warnings": tuple(warnings), "errors": tuple(errors)}


def _mark_invalid_plan(decision: FinalDecisionV1, legacy: Mapping[str, Any]) -> None:
    plan_keys = {"entry", "entry_price", "stop_loss", "stoploss", "target1", "target2", "target3"}
    if decision.action in {"BUY", "SELL"} and plan_keys.intersection(legacy) and decision.trade_plan is None:
        decision.authorization_status = AuthorizationStatus.BLOCKED.value
        decision.validation_errors.append("Legacy directional trade plan was incomplete or invalid.")
        decision.validation_passed = False


def build_dashboard_snapshot_v1(legacy_snapshot: Mapping[str, Any], *, reference_time: datetime | str | None = None) -> MarketSnapshotV1:
    """Adapt a dashboard snapshot only; does not mutate or fetch data."""
    return from_dashboard_snapshot(dict(legacy_snapshot), reference_time=reference_time)


def build_dashboard_decision_v1(legacy_response: Mapping[str, Any], snapshot_v1: MarketSnapshotV1, *, reference_time: datetime | str | None = None) -> FinalDecisionV1:
    """Adapt a dashboard response using the already-shadowed snapshot identity."""
    payload = dict(legacy_response)
    payload.setdefault("snapshot_id", snapshot_v1.snapshot_id)
    payload.setdefault("symbol", snapshot_v1.symbol)
    payload.setdefault("exchange", snapshot_v1.exchange)
    payload.setdefault("instrument_type", snapshot_v1.instrument_type)
    payload.setdefault("timestamp", snapshot_v1.market_timestamp.isoformat())
    decision = from_trade_engine_response(payload, reference_time=reference_time)
    _mark_invalid_plan(decision, payload)
    return decision


def build_live_option_snapshot_v1(*, symbol: str, exchange: str, market_timestamp: datetime | str, ltp: float | None, timeframes: Mapping[str, Any] | None = None, reference_time: datetime | str | None = None, **identity: Any) -> MarketSnapshotV1:
    """Adapt supplied live-analysis evidence only; no provider is consulted."""
    return from_live_analysis_inputs(symbol=symbol, exchange=exchange, market_timestamp=market_timestamp, ltp=ltp, timeframes=timeframes, reference_time=reference_time, **identity)


def build_live_option_decision_v1(legacy_response: Mapping[str, Any], snapshot_v1: MarketSnapshotV1, *, reference_time: datetime | str | None = None) -> FinalDecisionV1:
    payload = dict(legacy_response)
    payload.setdefault("snapshot_id", snapshot_v1.snapshot_id)
    payload.setdefault("symbol", snapshot_v1.symbol)
    payload.setdefault("exchange", snapshot_v1.exchange)
    payload.setdefault("instrument_type", snapshot_v1.instrument_type)
    payload.setdefault("timestamp", snapshot_v1.market_timestamp.isoformat())
    decision = from_live_option_pipeline_response(payload, reference_time=reference_time)
    _mark_invalid_plan(decision, payload)
    return decision


def validate_shadow_contracts(snapshot_v1: MarketSnapshotV1 | None, decision_v1: FinalDecisionV1 | None) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    if snapshot_v1 is None: errors.append("MarketSnapshot v1 was not built.")
    elif not snapshot_v1.validation_passed: errors.extend(snapshot_v1.critical_errors)
    else: warnings.extend(snapshot_v1.warnings)
    if decision_v1 is None: errors.append("FinalDecision v1 was not built.")
    elif not decision_v1.validation_passed: errors.extend(decision_v1.validation_errors)
    else: warnings.extend(decision_v1.warnings)
    return {"valid": not errors, "warnings": tuple(warnings), "errors": tuple(errors)}


def build_dashboard_shadow_contracts(legacy_snapshot: Mapping[str, Any], legacy_response: Mapping[str, Any], *, reference_time: datetime | str | None = None) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    snapshot: MarketSnapshotV1 | None = None
    decision: FinalDecisionV1 | None = None
    try:
        snapshot = build_dashboard_snapshot_v1(legacy_snapshot, reference_time=reference_time)
        warnings.extend(snapshot.warnings)
    except Exception as exc:  # Diagnostics must never interrupt the legacy response.
        errors.append(f"Dashboard snapshot shadow failed: {type(exc).__name__}.")
    if snapshot is not None:
        try:
            decision = build_dashboard_decision_v1(legacy_response, snapshot, reference_time=reference_time)
            warnings.extend(decision.warnings)
        except Exception as exc:
            errors.append(f"Dashboard decision shadow failed: {type(exc).__name__}.")
    validation = validate_shadow_contracts(snapshot, decision)
    warnings.extend(validation["warnings"])
    errors.extend(validation["errors"])
    return _result(snapshot, decision, list(dict.fromkeys(warnings)), list(dict.fromkeys(errors)))


def build_live_option_shadow_contracts(legacy_response: Mapping[str, Any], *, symbol: str, exchange: str, market_timestamp: datetime | str, ltp: float | None, timeframes: Mapping[str, Any] | None = None, reference_time: datetime | str | None = None, **identity: Any) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    snapshot: MarketSnapshotV1 | None = None
    decision: FinalDecisionV1 | None = None
    try:
        snapshot = build_live_option_snapshot_v1(symbol=symbol, exchange=exchange, market_timestamp=market_timestamp, ltp=ltp, timeframes=timeframes, reference_time=reference_time, **identity)
        warnings.extend(snapshot.warnings)
        decision = build_live_option_decision_v1(legacy_response, snapshot, reference_time=reference_time)
        warnings.extend(decision.warnings)
    except Exception as exc:
        errors.append(f"Live-option shadow failed: {type(exc).__name__}.")
    validation = validate_shadow_contracts(snapshot, decision)
    warnings.extend(validation["warnings"])
    errors.extend(validation["errors"])
    return _result(snapshot, decision, list(dict.fromkeys(warnings)), list(dict.fromkeys(errors)))


def compare_shadow_contracts(legacy_response: Mapping[str, Any], shadow: Mapping[str, Any]) -> dict[str, Any]:
    """Produce a stable diagnostic comparison; it makes no equivalence claim."""
    decision = shadow.get("decision_v1")
    snapshot = shadow.get("snapshot_v1")
    scores = {name: getattr(decision, name) if decision else None for name in ("confidence", "trade_quality_score", "institutional_score", "technical_score", "options_score", "risk_score", "data_quality_score")}
    missing_scores = tuple(name for name, value in scores.items() if value is None)
    return {"legacy_action_or_status": legacy_response.get("decision", legacy_response.get("final_decision", legacy_response.get("status"))), "v1_action": decision.action if decision else None, "v1_authorization": decision.authorization_status if decision else None, "v1_execution_status": decision.execution_status if decision else None, "mapping_warnings": tuple(shadow.get("warnings", ())), "mapping_errors": tuple(shadow.get("errors", ())), "blocking_reasons": tuple(decision.blocking_reasons) if decision else (), "score_values": scores, "missing_scores": missing_scores, "trade_plan_mapping": "VALID" if decision and decision.trade_plan else "UNAVAILABLE", "data_health_mapping": snapshot.overall_status if snapshot else "UNAVAILABLE"}


def serialize_shadow_contracts(shadow: Mapping[str, Any]) -> str:
    snapshot, decision = shadow.get("snapshot_v1"), shadow.get("decision_v1")
    payload = {"snapshot_v1": snapshot.to_dict() if snapshot else None, "decision_v1": decision.to_dict() if decision else None, "valid": bool(shadow.get("valid")), "warnings": list(shadow.get("warnings", ())), "errors": list(shadow.get("errors", ()))}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))

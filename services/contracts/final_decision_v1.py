"""Side-effect-free FinalDecision v1 contract and legacy response adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
import json
import math
from typing import Any, Mapping, Sequence
from uuid import uuid4
from zoneinfo import ZoneInfo


class DecisionValidationError(ValueError):
    """Raised for malformed timestamps or typed plan payloads."""


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    HOLD = "HOLD"


class AuthorizationStatus(str, Enum):
    BLOCKED = "BLOCKED"
    ANALYSIS_ONLY = "ANALYSIS_ONLY"
    PAPER_READY = "PAPER_READY"
    MANUAL_APPROVAL_REQUIRED = "MANUAL_APPROVAL_REQUIRED"
    AUTHORIZED = "AUTHORIZED"


class ExecutionStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


VALID_ACTIONS = {item.value for item in Action}
VALID_AUTHORIZATION = {item.value for item in AuthorizationStatus}
VALID_EXECUTION = {item.value for item in ExecutionStatus}
SCORE_NAMES = ("confidence", "trade_quality_score", "institutional_score", "technical_score", "options_score", "risk_score", "data_quality_score")


def _timestamp(value: datetime | str, timezone_name: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise DecisionValidationError("Timestamp must be ISO-8601.") from exc
    if not isinstance(value, datetime):
        raise DecisionValidationError("Timestamp must be a datetime or ISO-8601 string.")
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(timezone_name))
    return value.astimezone(ZoneInfo(timezone_name))


def _number(value: Any, *, minimum: float | None = None, maximum: float | None = None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result) or (minimum is not None and result < minimum) or (maximum is not None and result > maximum):
        return None
    return result


def _enum_value(value: Any) -> str:
    return value.value if isinstance(value, Enum) else str(value).upper()


def _texts(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


@dataclass(slots=True)
class TradePlanV1:
    entry_price: float | None = None
    entry_zone: tuple[float, float] | None = None
    stop_loss: float | None = None
    targets: tuple[float, ...] = ()
    quantity: float | None = None
    lots: float | None = None
    risk_reward_ratio: float | None = None
    maximum_planned_loss: float | None = None
    order_type: str = "MARKET"
    valid_until: datetime | str | None = None
    trailing_rule: str | None = None
    timezone: str = "Asia/Kolkata"

    def __post_init__(self) -> None:
        if (self.entry_price is None) == (self.entry_zone is None):
            raise DecisionValidationError("Trade plan needs exactly one entry_price or entry_zone.")
        if self.entry_price is not None:
            self.entry_price = _required_positive(self.entry_price, "entry_price")
        if self.entry_zone is not None:
            if len(self.entry_zone) != 2:
                raise DecisionValidationError("entry_zone must contain two prices.")
            self.entry_zone = tuple(_required_positive(value, "entry_zone") for value in self.entry_zone)  # type: ignore[assignment]
        self.stop_loss = _required_positive(self.stop_loss, "stop_loss")
        self.targets = tuple(_required_positive(value, "target") for value in self.targets)
        if not self.targets:
            raise DecisionValidationError("Trade plan needs at least one target.")
        for name in ("quantity", "lots", "maximum_planned_loss"):
            value = getattr(self, name)
            if value is not None:
                number = _number(value, minimum=0)
                if number is None:
                    raise DecisionValidationError(f"{name} must be finite and non-negative.")
                setattr(self, name, number)
        self.risk_reward_ratio = _required_positive(self.risk_reward_ratio, "risk_reward_ratio")
        if self.valid_until is not None:
            self.valid_until = _timestamp(self.valid_until, self.timezone)

    def to_dict(self) -> dict[str, Any]:
        return {"entry_price": self.entry_price, "entry_zone": list(self.entry_zone) if self.entry_zone else None, "stop_loss": self.stop_loss, "targets": list(self.targets), "quantity": self.quantity, "lots": self.lots, "risk_reward_ratio": self.risk_reward_ratio, "maximum_planned_loss": self.maximum_planned_loss, "order_type": self.order_type, "valid_until": self.valid_until.isoformat() if isinstance(self.valid_until, datetime) else None, "trailing_rule": self.trailing_rule}


def _required_positive(value: Any, name: str) -> float:
    number = _number(value, minimum=0)
    if number is None or number <= 0:
        raise DecisionValidationError(f"{name} must be positive and finite.")
    return number


@dataclass(slots=True)
class RiskSummary:
    risk_status: str = "UNKNOWN"
    risk_level: str = "UNKNOWN"
    capital: float | None = None
    risk_amount: float | None = None
    risk_percent: float | None = None
    position_size_valid: bool | None = None
    daily_limit_status: str = "UNKNOWN"
    exposure_status: str = "UNKNOWN"
    risk_errors: tuple[str, ...] = ()
    risk_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.risk_status = str(self.risk_status).upper()
        for name in ("capital", "risk_amount"):
            value = getattr(self, name)
            if value is not None and _number(value, minimum=0) is None:
                raise DecisionValidationError(f"{name} must be finite and non-negative.")
            if value is not None:
                setattr(self, name, float(value))
        if self.risk_percent is not None:
            self.risk_percent = _required_score(self.risk_percent, "risk_percent")
        self.risk_errors, self.risk_warnings = _texts(self.risk_errors), _texts(self.risk_warnings)

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in ("risk_status", "risk_level", "capital", "risk_amount", "risk_percent", "position_size_valid", "daily_limit_status", "exposure_status", "risk_errors", "risk_warnings")}


@dataclass(slots=True)
class DataHealthSummary:
    overall_status: str = "UNKNOWN"
    validation_passed: bool = True
    missing_sources: tuple[str, ...] = ()
    stale_sources: tuple[str, ...] = ()
    critical_errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.overall_status = str(self.overall_status).upper()
        self.missing_sources, self.stale_sources = _texts(self.missing_sources), _texts(self.stale_sources)
        self.critical_errors, self.warnings = _texts(self.critical_errors), _texts(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        return {name: list(getattr(self, name)) if isinstance(getattr(self, name), tuple) else getattr(self, name) for name in ("overall_status", "validation_passed", "missing_sources", "stale_sources", "critical_errors", "warnings")}


@dataclass(slots=True)
class FinalDecisionV1:
    snapshot_id: str
    symbol: str
    exchange: str
    instrument_type: str
    created_at: datetime | str
    market_timestamp: datetime | str
    action: str = Action.WAIT
    authorization_status: str = AuthorizationStatus.ANALYSIS_ONLY
    execution_status: str = ExecutionStatus.NOT_REQUESTED
    schema_version: str = "final_decision.v1"
    decision_id: str = field(default_factory=lambda: str(uuid4()))
    expiry: str | None = None
    strike: float | None = None
    option_type: str | None = None
    timezone: str = "Asia/Kolkata"
    market_regime: str = "UNKNOWN"
    direction: str = "NEUTRAL"
    trend_strength: str | None = None
    volatility_state: str | None = None
    market_session: str = "UNKNOWN"
    confidence: float | None = None
    trade_quality_score: float | None = None
    institutional_score: float | None = None
    technical_score: float | None = None
    options_score: float | None = None
    risk_score: float | None = None
    data_quality_score: float | None = None
    trade_plan: TradePlanV1 | None = None
    risk: RiskSummary = field(default_factory=RiskSummary)
    supporting_reasons: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    options_interpretation: Mapping[str, Any] = field(default_factory=dict)
    data_health: DataHealthSummary = field(default_factory=DataHealthSummary)
    audit_id: str | None = None
    engine_versions: Mapping[str, str] = field(default_factory=dict)
    rule_versions: Mapping[str, str] = field(default_factory=dict)
    source_timestamps: Mapping[str, str] = field(default_factory=dict)
    trace_metadata: Mapping[str, Any] = field(default_factory=dict)
    internal_errors: tuple[str, ...] = ()
    validation_errors: list[str] = field(default_factory=list)
    validation_passed: bool = field(init=False)

    def __post_init__(self) -> None:
        self.created_at, self.market_timestamp = _timestamp(self.created_at, self.timezone), _timestamp(self.market_timestamp, self.timezone)
        self.action, self.authorization_status, self.execution_status = _enum_value(self.action), _enum_value(self.authorization_status), _enum_value(self.execution_status)
        self._validate_identity()
        self._validate_scores()
        for name in ("supporting_reasons", "contradictions", "blocking_reasons", "invalidation_conditions", "warnings", "internal_errors"):
            setattr(self, name, _texts(getattr(self, name)))
        self._validate_json_metadata()
        self._apply_safety_invariants()
        self.validation_passed = not self.validation_errors

    def _validate_identity(self) -> None:
        if self.schema_version != "final_decision.v1": self.validation_errors.append("Unsupported schema version.")
        for name in ("decision_id", "snapshot_id", "symbol", "exchange", "instrument_type"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip(): self.validation_errors.append(f"{name} is required.")
        if self.action not in VALID_ACTIONS: self.validation_errors.append("Invalid action.")
        if self.authorization_status not in VALID_AUTHORIZATION: self.validation_errors.append("Invalid authorization status.")
        if self.execution_status not in VALID_EXECUTION: self.validation_errors.append("Invalid execution status.")
        if self.expiry is not None:
            try: date.fromisoformat(self.expiry)
            except (TypeError, ValueError): self.validation_errors.append("expiry must be YYYY-MM-DD when supplied.")
        if self.strike is not None:
            value = _number(self.strike, minimum=0)
            if value is None or value <= 0: self.validation_errors.append("strike must be positive and finite.")
            else: self.strike = value
        if self.option_type is not None:
            self.option_type = str(self.option_type).upper()
            if self.option_type not in {"CE", "PE"}: self.validation_errors.append("option_type must be CE or PE when supplied.")

    def _validate_scores(self) -> None:
        for name in SCORE_NAMES:
            value = getattr(self, name)
            if value is not None:
                score = _number(value, minimum=0, maximum=100)
                if score is None: self.validation_errors.append(f"{name} must be finite and in 0..100.")
                else: setattr(self, name, score)

    def _validate_json_metadata(self) -> None:
        for name in ("options_interpretation", "engine_versions", "rule_versions", "source_timestamps", "trace_metadata"):
            try: json.dumps(getattr(self, name), sort_keys=True)
            except (TypeError, ValueError):
                self.validation_errors.append(f"{name} must be JSON-serializable.")
                setattr(self, name, {})

    def _block(self, reason: str) -> None:
        self.validation_errors.append(reason)
        self.authorization_status = AuthorizationStatus.BLOCKED.value
        if self.execution_status in {ExecutionStatus.PENDING.value, ExecutionStatus.SUBMITTED.value, ExecutionStatus.FILLED.value, ExecutionStatus.PARTIALLY_FILLED.value}:
            self.execution_status = ExecutionStatus.REJECTED.value

    def _apply_safety_invariants(self) -> None:
        if self.validation_errors: self._block("Invalid identity, score, or metadata prevents authorization.")
        if self.data_health.critical_errors or not self.data_health.validation_passed or self.data_health.overall_status in {"INVALID", "FAILED"}: self._block("Invalid data health prevents authorization.")
        if self.risk.risk_status in {"REJECTED", "FAILED", "INVALID"}: self._block("Risk rejection prevents authorization.")
        directional = self.action in {Action.BUY.value, Action.SELL.value}
        execution_ready = self.authorization_status in {AuthorizationStatus.PAPER_READY.value, AuthorizationStatus.MANUAL_APPROVAL_REQUIRED.value, AuthorizationStatus.AUTHORIZED.value}
        if self.action == Action.WAIT.value and self.authorization_status == AuthorizationStatus.AUTHORIZED.value: self._block("WAIT cannot be authorized for execution.")
        if self.action == Action.HOLD.value and self.execution_status not in {ExecutionStatus.NOT_REQUESTED.value, ExecutionStatus.REJECTED.value, ExecutionStatus.CANCELLED.value, ExecutionStatus.FAILED.value}: self._block("HOLD cannot open a new trade.")
        if self.authorization_status == AuthorizationStatus.BLOCKED.value and self.execution_status in {ExecutionStatus.SUBMITTED.value, ExecutionStatus.FILLED.value, ExecutionStatus.PARTIALLY_FILLED.value}: self._block("BLOCKED decision cannot be submitted or filled.")
        if directional and execution_ready and self.trade_plan is None: self._block("Execution-ready directional action requires a trade plan.")
        if directional and self.trade_plan is None and self.authorization_status not in {AuthorizationStatus.ANALYSIS_ONLY.value, AuthorizationStatus.BLOCKED.value}: self._block("Direction without plan must be analysis-only or blocked.")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in ("schema_version", "decision_id", "snapshot_id", "symbol", "exchange", "instrument_type", "expiry", "strike", "option_type", "timezone", "market_regime", "direction", "trend_strength", "volatility_state", "market_session", "action", "authorization_status", "execution_status", *SCORE_NAMES, "audit_id")}
        result.update({"created_at": self.created_at.isoformat(), "market_timestamp": self.market_timestamp.isoformat(), "trade_plan": self.trade_plan.to_dict() if self.trade_plan else None, "risk": self.risk.to_dict(), "supporting_reasons": list(self.supporting_reasons), "contradictions": list(self.contradictions), "blocking_reasons": list(self.blocking_reasons), "invalidation_conditions": list(self.invalidation_conditions), "warnings": list(self.warnings), "options_interpretation": dict(self.options_interpretation), "data_health": self.data_health.to_dict(), "engine_versions": dict(sorted(self.engine_versions.items())), "rule_versions": dict(sorted(self.rule_versions.items())), "source_timestamps": dict(sorted(self.source_timestamps.items())), "trace_metadata": dict(self.trace_metadata), "internal_errors": list(self.internal_errors), "validation_errors": list(self.validation_errors), "validation_passed": self.validation_passed})
        return result

    def to_json(self) -> str: return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FinalDecisionV1":
        plan_data = payload.get("trade_plan")
        return cls(
            snapshot_id=payload.get("snapshot_id", ""), symbol=payload.get("symbol", ""),
            exchange=payload.get("exchange", ""), instrument_type=payload.get("instrument_type", ""),
            created_at=payload["created_at"], market_timestamp=payload["market_timestamp"],
            action=payload.get("action", Action.WAIT.value), authorization_status=payload.get("authorization_status", AuthorizationStatus.BLOCKED.value),
            execution_status=payload.get("execution_status", ExecutionStatus.NOT_REQUESTED.value), schema_version=payload.get("schema_version", "final_decision.v1"),
            decision_id=payload.get("decision_id", str(uuid4())), expiry=payload.get("expiry"), strike=payload.get("strike"), option_type=payload.get("option_type"), timezone=payload.get("timezone", "Asia/Kolkata"),
            market_regime=payload.get("market_regime", "UNKNOWN"), direction=payload.get("direction", "NEUTRAL"), trend_strength=payload.get("trend_strength"), volatility_state=payload.get("volatility_state"), market_session=payload.get("market_session", "UNKNOWN"),
            confidence=payload.get("confidence"), trade_quality_score=payload.get("trade_quality_score"), institutional_score=payload.get("institutional_score"), technical_score=payload.get("technical_score"), options_score=payload.get("options_score"), risk_score=payload.get("risk_score"), data_quality_score=payload.get("data_quality_score"),
            trade_plan=TradePlanV1(**plan_data) if isinstance(plan_data, Mapping) else None,
            risk=RiskSummary(**payload.get("risk", {})), data_health=DataHealthSummary(**payload.get("data_health", {})),
            supporting_reasons=tuple(payload.get("supporting_reasons", ())), contradictions=tuple(payload.get("contradictions", ())), blocking_reasons=tuple(payload.get("blocking_reasons", ())), invalidation_conditions=tuple(payload.get("invalidation_conditions", ())), warnings=tuple(payload.get("warnings", ())), options_interpretation=payload.get("options_interpretation", {}), audit_id=payload.get("audit_id"), engine_versions=payload.get("engine_versions", {}), rule_versions=payload.get("rule_versions", {}), source_timestamps=payload.get("source_timestamps", {}), trace_metadata=payload.get("trace_metadata", {}), internal_errors=tuple(payload.get("internal_errors", ())), validation_errors=list(payload.get("validation_errors", ())),
        )


def _plan_from_legacy(data: Mapping[str, Any]) -> TradePlanV1 | None:
    entry, stop = data.get("entry", data.get("entry_price")), data.get("stop_loss", data.get("stoploss"))
    targets = tuple(value for value in (data.get("target1"), data.get("target2"), data.get("target3")) if value is not None)
    if entry is None or stop is None or not targets: return None
    try: return TradePlanV1(entry_price=entry, stop_loss=stop, targets=targets, quantity=data.get("quantity"), lots=data.get("lots"), risk_reward_ratio=data.get("risk_reward_ratio", data.get("rr", 1)), maximum_planned_loss=data.get("maximum_planned_loss"))
    except DecisionValidationError: return None


def _legacy_action(value: Any, direction: Any = None) -> tuple[str, str | None, str | None]:
    value, direction = str(value or "").upper(), str(direction or "").upper()
    if value in {"BUY", "BUY CE", "BUY_CALL"}: return Action.BUY.value, "CE" if value == "BUY CE" else None, None
    if value in {"SELL", "BUY PE", "BUY_PUT"}: return Action.SELL.value, "PE" if value == "BUY PE" else None, None
    if value in {"WAIT", "NO_TRADE", "MARKET_CLOSED", "MARKET_HOLIDAY", "STALE_MARKET_DATA", "TRADE_REJECTED", "ERROR", "NO_CONTRACT"}: return Action.WAIT.value, None, None
    if value == "HOLD": return Action.HOLD.value, None, None
    if value in {"TRADE_READY", "TRADE_ALLOWED"} and direction in {"BULLISH", "BUY"}: return Action.BUY.value, None, None
    if value in {"TRADE_READY", "TRADE_ALLOWED"} and direction in {"BEARISH", "SELL"}: return Action.SELL.value, None, None
    return Action.WAIT.value, None, f"Unsupported or ambiguous legacy status: {value or 'missing'}."


def _from_legacy(data: Mapping[str, Any], *, source: str, reference_time: datetime | str | None = None) -> FinalDecisionV1:
    warnings: list[str] = []
    raw_status = data.get("decision", data.get("final_decision", data.get("status")))
    action, option_type, mapping_warning = _legacy_action(raw_status, data.get("direction", data.get("trend")))
    if mapping_warning: warnings.append(mapping_warning)
    plan = _plan_from_legacy(data)
    status = str(raw_status or "").upper()
    approval = AuthorizationStatus.BLOCKED.value
    if action in {Action.BUY.value, Action.SELL.value} and plan is not None:
        if status == "TRADE_READY": approval = AuthorizationStatus.MANUAL_APPROVAL_REQUIRED.value
        elif status == "TRADE_ALLOWED" and data.get("approval_status") == "APPROVED" and data.get("entry_allowed") is True: approval = AuthorizationStatus.PAPER_READY.value
        elif status not in {"TRADE_READY", "TRADE_ALLOWED"}: approval = AuthorizationStatus.ANALYSIS_ONLY.value
    elif status in {"TRADE_READY", "TRADE_ALLOWED"}: warnings.append("Legacy directional authorization lacked a verified trade plan; blocked.")
    snapshot = data.get("snapshot") if isinstance(data.get("snapshot"), Mapping) else {}
    snapshot_id = str(data.get("snapshot_id") or snapshot.get("snapshot_id") or "")
    if not snapshot_id: warnings.append("Legacy input has no snapshot_id; contract is blocked for compatibility.")
    now = reference_time or datetime.now(ZoneInfo("Asia/Kolkata"))
    market_timestamp = data.get("timestamp") or snapshot.get("timestamp") or now
    health = DataHealthSummary(overall_status="INVALID" if not snapshot_id else "UNKNOWN", validation_passed=bool(snapshot_id), critical_errors=("Missing snapshot_id.",) if not snapshot_id else ())
    known = {"decision", "final_decision", "status", "direction", "trend", "entry", "entry_price", "stop_loss", "stoploss", "target1", "target2", "target3", "quantity", "lots", "risk_reward_ratio", "rr", "maximum_planned_loss", "approval_status", "entry_allowed", "snapshot", "snapshot_id", "symbol", "exchange", "instrument_type", "timestamp", "confidence", "decision_score", "institutional_score", "reason", "reasons", "trade_plan", "selected_contract", "audit_trail", "risk_level", "risk"}
    unmapped = sorted(set(data) - known)
    if unmapped: warnings.append("Unmapped legacy fields: " + ", ".join(unmapped))
    reasons = _texts(data.get("reasons")) or ((str(data["reason"]),) if data.get("reason") else ())
    return FinalDecisionV1(snapshot_id=snapshot_id, symbol=str(data.get("symbol") or snapshot.get("symbol") or "UNKNOWN"), exchange=str(data.get("exchange") or snapshot.get("exchange") or "UNKNOWN"), instrument_type=str(data.get("instrument_type") or snapshot.get("instrument_type") or "UNKNOWN"), created_at=now, market_timestamp=market_timestamp, action=action, authorization_status=approval, option_type=option_type, confidence=data.get("confidence"), trade_quality_score=data.get("decision_score"), institutional_score=data.get("institutional_score"), trade_plan=plan, risk=RiskSummary(risk_level=data.get("risk_level", "UNKNOWN")), supporting_reasons=reasons, blocking_reasons=(str(data.get("reason")),) if approval == AuthorizationStatus.BLOCKED.value and data.get("reason") else (), warnings=tuple(warnings), data_health=health, trace_metadata={"legacy_source": source})


def from_trade_engine_response(data: Mapping[str, Any], reference_time: datetime | str | None = None) -> FinalDecisionV1: return _from_legacy(data, source="trade_engine", reference_time=reference_time)
def from_live_option_pipeline_response(data: Mapping[str, Any], reference_time: datetime | str | None = None) -> FinalDecisionV1: return _from_legacy(data, source="live_option_pipeline", reference_time=reference_time)
def from_master_decision_response(data: Mapping[str, Any], reference_time: datetime | str | None = None) -> FinalDecisionV1: return _from_legacy(data, source="master_decision", reference_time=reference_time)


def to_legacy_dashboard_dict(decision: FinalDecisionV1) -> dict[str, Any]:
    plan = decision.trade_plan
    return {"decision": "BUY CE" if decision.action == "BUY" and decision.option_type == "CE" else "BUY PE" if decision.action == "SELL" and decision.option_type == "PE" else decision.action, "confidence": decision.confidence, "reason": " | ".join(decision.supporting_reasons or decision.blocking_reasons), "entry": plan.entry_price if plan else None, "stop_loss": plan.stop_loss if plan else None, "target1": plan.targets[0] if plan and plan.targets else None, "approval_status": decision.authorization_status, "entry_allowed": decision.authorization_status in {"PAPER_READY", "AUTHORIZED"}, "final_decision_v1_warnings": list(decision.warnings) + list(decision.validation_errors)}


def to_paper_execution_candidate(decision: FinalDecisionV1) -> dict[str, Any] | None:
    if decision.action not in {"BUY", "SELL"} or decision.authorization_status not in {"PAPER_READY", "AUTHORIZED"} or decision.execution_status != "NOT_REQUESTED" or decision.trade_plan is None or not decision.validation_passed: return None
    plan = decision.trade_plan
    return {"decision": decision.action, "master_decision": decision.action, "approval_status": "APPROVED", "entry_allowed": True, "trade_action": "EXECUTE", "entry": plan.entry_price, "stop_loss": plan.stop_loss, "target1": plan.targets[0], "target2": plan.targets[1] if len(plan.targets) > 1 else plan.targets[0], "target3": plan.targets[2] if len(plan.targets) > 2 else plan.targets[-1], "confidence": decision.confidence or 0.0, "quantity": plan.quantity, "snapshot": {"timestamp": decision.market_timestamp.isoformat(), "ltp": plan.entry_price}}

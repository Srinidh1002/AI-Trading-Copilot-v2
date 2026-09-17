"""Durable Task 9 authority for a selected PAPER entry awaiting its zone."""
from __future__ import annotations

from services.certification.task9_atomic_file_replace import replace_task9_atomic_file

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from services.contracts.integrated_three_target_trade_plan_result_v1 import IntegratedThreeTargetTradePlanResultV1
from services.contracts.paper_market_observation_v1 import PaperMarketObservationV1
from services.contracts.paper_portfolio_policy_v1 import PaperPortfolioPolicyV1
from services.contracts.paper_trade_lifecycle_policy_v1 import PaperTradeLifecyclePolicyV1
from services.contracts.paper_trade_lifecycle_state_v1 import PaperTradeLifecycleStateV1
from services.contracts.entry_zone_evaluation_result_v1 import EntryZoneEvaluationResultV1
from services.contracts.stop_loss_evaluation_result_v1 import StopLossEvaluationResultV1
from services.contracts.three_target_evaluation_result_v1 import ThreeTargetEvaluationResultV1
from services.contracts.trade_plan_target_v1 import TradePlanTargetV1
from services.contracts.option_contract_v1 import OptionContractV1
from services.contracts.option_contract_candidate_v1 import OptionContractCandidateV1
from services.contracts.option_contract_selection_result_v1 import OptionContractSelectionResultV1
from services.contracts.capital_quantity_planning_result_v1 import CapitalQuantityPlanningResultV1
from services.paper_orchestration.new_entry_paper_lifecycle_executor import NewEntryPaperLifecycleInputV1


def _timestamps(value):
    if type(value) is not dict:
        raise ValueError("source_timestamps")
    return {key: datetime.fromisoformat(item) for key, item in value.items()}


def _result_values(raw, *, tuple_fields=()):
    if type(raw) is not dict:
        raise ValueError("nested result")
    value = dict(raw)
    value["evaluated_at"] = datetime.fromisoformat(value["evaluated_at"])
    value["source_timestamps"] = _timestamps(value.get("source_timestamps", {}))
    for name in tuple_fields:
        value[name] = tuple(value.get(name, ()))
    return value


def _restore_option_contract(raw):
    value = dict(raw)
    value["expiry_date"] = date.fromisoformat(value["expiry_date"])
    value["market_timestamp"] = datetime.fromisoformat(value["market_timestamp"])
    return OptionContractV1(**value)


def _restore_candidate(raw):
    value = dict(raw)
    value["contract"] = _restore_option_contract(value["contract"])
    value["rejection_reasons"] = tuple(value.get("rejection_reasons", ()))
    value["warnings"] = tuple(value.get("warnings", ()))
    for name in ("schema_version", "eligible", "execution_mode", "live_execution_eligible"):
        value.pop(name, None)
    return OptionContractCandidateV1(**value)


def _restore_selection(raw):
    value = _result_values(
        raw,
        tuple_fields=("selected_reason_codes", "blockers", "warnings", "decision_reasons"),
    )
    selected = value.get("selected_contract")
    value["selected_contract"] = None if selected is None else _restore_candidate(selected)
    return OptionContractSelectionResultV1(**value)


def _restore_entry_zone(raw):
    return EntryZoneEvaluationResultV1(**_result_values(
        raw, tuple_fields=("blockers", "warnings", "decision_reasons"),
    ))


def _restore_stop_loss(raw):
    return StopLossEvaluationResultV1(**_result_values(
        raw, tuple_fields=("blockers", "warnings", "decision_reasons", "invalidation_rules"),
    ))


def _restore_targets(raw):
    value = _result_values(raw, tuple_fields=("blockers", "warnings", "decision_reasons"))
    for name in ("target_1", "target_2", "target_3"):
        value[name] = None if value[name] is None else TradePlanTargetV1(**value[name])
    return ThreeTargetEvaluationResultV1(**value)


def _restore_capital(raw):
    return CapitalQuantityPlanningResultV1(**_result_values(
        raw, tuple_fields=("blockers", "warnings", "decision_reasons"),
    ))


def _restore_integrated_plan(raw):
    if type(raw) is not dict:
        raise ValueError("integrated_trade_plan_result")
    value = dict(raw)
    required = {
        "integration_id", "status", "entry_zone_result", "stop_loss_result",
        "three_target_result", "option_contract_selection_result",
        "capital_quantity_result", "blockers", "warnings", "decision_reasons",
        "metadata", "execution_mode", "live_execution_eligible", "schema_version",
    }
    if not required.issubset(value):
        raise ValueError("integrated_trade_plan_result keys are incomplete")
    return IntegratedThreeTargetTradePlanResultV1(
        integration_id=value["integration_id"], status=value["status"],
        # This field is absent from the established v1 serialized schema.
        canonical_trade_plan_input=None,
        entry_zone_result=_restore_entry_zone(value["entry_zone_result"]),
        stop_loss_result=_restore_stop_loss(value["stop_loss_result"]),
        three_target_result=_restore_targets(value["three_target_result"]),
        option_contract_selection_result=_restore_selection(value["option_contract_selection_result"]),
        capital_quantity_result=_restore_capital(value["capital_quantity_result"]),
        blockers=tuple(value["blockers"]), warnings=tuple(value["warnings"]),
        decision_reasons=tuple(value["decision_reasons"]), metadata=value["metadata"],
        execution_mode=value["execution_mode"],
        live_execution_eligible=value["live_execution_eligible"], schema_version=value["schema_version"],
    )


def _restore_observation(raw):
    value = dict(raw)
    value["observed_at"] = datetime.fromisoformat(value["observed_at"])
    value["received_at"] = datetime.fromisoformat(value["received_at"])
    value["market_session_date"] = date.fromisoformat(value["market_session_date"])
    value["source_timestamps"] = {key: datetime.fromisoformat(item) for key, item in value["source_timestamps"].items()}
    value["warnings"] = tuple(value["warnings"])
    return PaperMarketObservationV1(**value)


def _restore_policy(raw, cls):
    value = dict(raw)
    for key in ("policy_timestamp",):
        if key in value:
            value[key] = datetime.fromisoformat(value[key])
    if "source_timestamps" in value:
        value["source_timestamps"] = {key: datetime.fromisoformat(item) for key, item in value["source_timestamps"].items()}
    if "warnings" in value:
        value["warnings"] = tuple(value["warnings"])
    return cls(**value)


def _restore_state(raw):
    value = dict(raw)
    for key in ("lifecycle_created_at", "last_observation_timestamp", "waiting_for_entry_at", "opened_at", "partially_exited_at", "closed_at", "cancelled_at", "blocked_at"):
        if value.get(key) is not None:
            value[key] = datetime.fromisoformat(value[key])
    for key in ("blockers", "decision_reasons", "warnings"):
        value[key] = tuple(value[key])
    return PaperTradeLifecycleStateV1(**value)


@dataclass(frozen=True, slots=True)
class Task9PendingEntryV1:
    prediction_id: str
    parent_cycle_id: str
    market: str
    option_symbol: str
    input_value: NewEntryPaperLifecycleInputV1
    lifecycle_state: PaperTradeLifecycleStateV1
    status: str = "WAITING_FOR_ENTRY"
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self):
        if type(self.prediction_id) is not str or not self.prediction_id.strip() or type(self.parent_cycle_id) is not str or not self.parent_cycle_id.strip(): raise ValueError("pending identity")
        if self.market not in {"NIFTY", "SENSEX"} or type(self.option_symbol) is not str or not self.option_symbol.strip(): raise ValueError("pending market")
        if type(self.input_value) is not NewEntryPaperLifecycleInputV1 or type(self.lifecycle_state) is not PaperTradeLifecycleStateV1: raise TypeError("pending authority")
        if self.input_value.prediction_id != self.prediction_id or self.input_value.observation.market != self.market or self.input_value.observation.option_symbol != self.option_symbol: raise ValueError("pending input identity")
        if self.status not in {"WAITING_FOR_ENTRY", "OPEN", "CLOSED_INVALIDATED", "CLOSED_SESSION", "CLOSED_EXPIRY", "BLOCKED"}: raise ValueError("pending status")
        if self.status == "WAITING_FOR_ENTRY" and (self.lifecycle_state.current_state != "WAITING_FOR_ENTRY" or self.lifecycle_state.is_terminal): raise ValueError("pending waiting state")
        if self.status != "WAITING_FOR_ENTRY" and self.lifecycle_state.current_state != self.status: raise ValueError("pending terminal state")
        if self.execution_mode != "PAPER" or self.broker_order_submission or self.live_execution_eligible: raise ValueError("PAPER pending authority")

    def to_dict(self):
        value = self.input_value
        return {"prediction_id": self.prediction_id, "parent_cycle_id": self.parent_cycle_id, "market": self.market, "option_symbol": self.option_symbol, "status": self.status, "lifecycle_state": self.lifecycle_state.to_dict(), "input": {name: getattr(value, name) for name in ("portfolio_id", "initial_portfolio_snapshot_id", "admission_result_id", "admission_request_id", "admission_idempotency_key", "admission_portfolio_event_id", "requested_reservation_id", "paper_trade_id", "paper_trade_adapter_idempotency_key", "initial_lifecycle_state_id", "resulting_lifecycle_state_id", "requested_transition_id", "position_id", "entry_fill_id", "activation_result_snapshot_id", "activation_portfolio_event_id", "activation_update_idempotency_key", "trading_day_id", "starting_capital") } | {"evaluated_at": value.evaluated_at.isoformat(), "prediction_id": value.prediction_id, "integrated_trade_plan_result": value.integrated_trade_plan_result.to_dict(), "portfolio_policy": value.portfolio_policy.to_dict(), "lifecycle_policy": value.lifecycle_policy.to_dict(), "observation": value.observation.to_dict()}, "execution_mode": "PAPER", "broker_order_submission": False, "live_execution_eligible": False}

    @classmethod
    def from_dict(cls, raw):
        try:
            value = dict(raw); input_raw = dict(value.pop("input"))
            plan_raw = input_raw.pop("integrated_trade_plan_result")
            plan = _restore_integrated_plan(plan_raw)
            input_value = NewEntryPaperLifecycleInputV1(**{**input_raw, "evaluated_at": datetime.fromisoformat(input_raw["evaluated_at"]), "integrated_trade_plan_result": plan, "portfolio_policy": _restore_policy(input_raw.pop("portfolio_policy"), PaperPortfolioPolicyV1), "lifecycle_policy": _restore_policy(input_raw.pop("lifecycle_policy"), PaperTradeLifecyclePolicyV1), "observation": _restore_observation(input_raw.pop("observation"))})
            return cls(input_value=input_value, lifecycle_state=_restore_state(value.pop("lifecycle_state")), **value)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid Task 9 pending-entry payload") from exc


class Task9PendingEntryStore:
    def __init__(self, file_path: str | Path): self.file_path = Path(file_path)
    def _read(self):
        if not self.file_path.exists(): return {"version": 1, "entries": {}}
        value = json.loads(self.file_path.read_text(encoding="utf-8"))
        if type(value) is not dict or set(value) != {"version", "entries"} or value["version"] != 1 or type(value["entries"]) is not dict: raise ValueError("invalid Task 9 pending-entry store")
        return value
    def save(self, entry: Task9PendingEntryV1):
        if type(entry) is not Task9PendingEntryV1: raise TypeError("entry")
        doc = self._read(); raw = entry.to_dict(); existing = doc["entries"].get(entry.prediction_id)
        if existing is not None and existing == raw: return "DUPLICATE_SAME_PAYLOAD"
        if existing is not None and Task9PendingEntryV1.from_dict(existing).status != "WAITING_FOR_ENTRY": return "TERMINAL"
        doc["entries"][entry.prediction_id] = raw; self.file_path.parent.mkdir(parents=True, exist_ok=True); tmp = self.file_path.with_suffix(self.file_path.suffix + ".tmp")
        try: tmp.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False), encoding="utf-8"); replace_task9_atomic_file(tmp, self.file_path)
        finally: tmp.unlink(missing_ok=True)
        return "SAVED"
    def recover(self, prediction_id: str):
        raw = self._read()["entries"].get(prediction_id); return None if raw is None else Task9PendingEntryV1.from_dict(raw)

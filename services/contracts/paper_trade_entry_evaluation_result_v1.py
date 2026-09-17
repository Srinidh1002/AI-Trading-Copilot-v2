"""Immutable result for a pure PAPER entry-transition evaluation."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from .paper_market_observation_v1 import (
    _aware_datetime,
    _finite_number,
    _freeze_json_value,
    _freeze_warnings,
    _nonblank_text,
    _plain_json_value,
)
from .paper_trade_fill_v1 import PaperTradeFillV1
from .paper_trade_position_v1 import PaperTradePositionV1


@dataclass(frozen=True, slots=True)
class PaperTradeEntryEvaluationResultV1:
    entry_evaluation_result_id: str; requested_transition_id: str; trade_plan_id: str
    integrated_trade_plan_result_id: str; lifecycle_policy_id: str
    source_lifecycle_state_id: str; observation_id: str; status: str
    entry_decision: str; resulting_lifecycle_state: str; entry_price_basis: str
    evaluated_entry_price: float; effective_entry_zone_lower: float
    effective_entry_zone_upper: float; preferred_entry: float; entry_activated: bool
    observation_timestamp: datetime; observation_fresh: bool; observation_order_valid: bool
    session_entry_allowed: bool; expiry_entry_allowed: bool
    position: PaperTradePositionV1 | None = None; entry_fill: PaperTradeFillV1 | None = None
    blockers: tuple[str, ...] = (); decision_reasons: tuple[str, ...] = (); warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"; live_execution_eligible: bool = False; schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in ("entry_evaluation_result_id", "requested_transition_id", "trade_plan_id", "integrated_trade_plan_result_id", "lifecycle_policy_id", "source_lifecycle_state_id", "observation_id"):
            object.__setattr__(self, name, _nonblank_text(getattr(self, name), name))
        allowed = {
            "BLOCKED": ("BLOCK", "BLOCKED"), "WAITING_FOR_ENTRY": ("WAIT", "PLANNED"),
            "OPEN": ("ACTIVATE", "OPEN"), "CLOSED_INVALIDATED": ("INVALIDATE", "CLOSED_INVALIDATED"),
            "CLOSED_SESSION": ("SESSION_CLOSE", "CLOSED_SESSION"), "CLOSED_EXPIRY": ("EXPIRY_CLOSE", "CLOSED_EXPIRY"),
        }
        if self.status not in allowed or self.entry_decision != allowed[self.status][0]: raise ValueError("status/decision")
        if self.status == "WAITING_FOR_ENTRY" and self.resulting_lifecycle_state not in {"PLANNED", "WAITING_FOR_ENTRY"}: raise ValueError("waiting state")
        if self.status != "WAITING_FOR_ENTRY" and self.resulting_lifecycle_state != allowed[self.status][1]: raise ValueError("resulting state")
        if self.entry_price_basis != "SELECTED_OPTION_PREMIUM": raise ValueError("entry_price_basis")
        for name in ("evaluated_entry_price", "effective_entry_zone_lower", "effective_entry_zone_upper", "preferred_entry"):
            object.__setattr__(self, name, _finite_number(getattr(self, name), name, required=True, minimum=0.0, strictly_greater=True))
        if self.effective_entry_zone_lower > self.effective_entry_zone_upper: raise ValueError("entry zone")
        object.__setattr__(self, "observation_timestamp", _aware_datetime(self.observation_timestamp, "observation_timestamp"))
        for name in ("entry_activated", "observation_fresh", "observation_order_valid", "session_entry_allowed", "expiry_entry_allowed"):
            if type(getattr(self, name)) is not bool: raise TypeError(name)
        object.__setattr__(self, "blockers", _freeze_warnings(self.blockers)); object.__setattr__(self, "decision_reasons", _freeze_warnings(self.decision_reasons)); object.__setattr__(self, "warnings", _freeze_warnings(self.warnings))
        open_result = self.status == "OPEN"
        if self.entry_activated != open_result: raise ValueError("entry_activated")
        if open_result:
            if type(self.position) is not PaperTradePositionV1 or type(self.entry_fill) is not PaperTradeFillV1 or self.blockers: raise ValueError("open result")
            if self.position.entry_fill != self.entry_fill or self.position.position_id != self.entry_fill.position_id or self.position.trade_plan_id != self.trade_plan_id or self.position.integrated_trade_plan_result_id != self.integrated_trade_plan_result_id: raise ValueError("open identity")
        elif self.position is not None or self.entry_fill is not None: raise ValueError("non-open result")
        if self.status == "BLOCKED" and not self.blockers: raise ValueError("blocked result")
        if self.status == "WAITING_FOR_ENTRY" and (self.blockers or not self.decision_reasons): raise ValueError("waiting result")
        object.__setattr__(self, "metadata", _freeze_json_value(self.metadata))
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.schema_version != "1.0": raise ValueError("PAPER-only schema")

    def to_dict(self) -> dict[str, Any]:
        return {name: (self.position.to_dict() if name == "position" and self.position else self.entry_fill.to_dict() if name == "entry_fill" and self.entry_fill else self.observation_timestamp.isoformat() if name == "observation_timestamp" else _plain_json_value(self.metadata) if name == "metadata" else list(getattr(self, name)) if name in {"blockers", "decision_reasons", "warnings"} else getattr(self, name)) for name in self.__dataclass_fields__}
    def to_json(self) -> str: return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    def semantic_dict(self) -> dict[str, Any]:
        value = self.to_dict(); value.pop("entry_evaluation_result_id"); return value

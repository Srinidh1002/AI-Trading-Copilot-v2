"""Immutable lifecycle state and deterministic transition validation for PAPER trades."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

CANONICAL_PAPER_TRADE_LIFECYCLE_STATES = frozenset({"PLANNED", "WAITING_FOR_ENTRY", "OPEN", "PARTIALLY_EXITED", "CLOSED_TARGET_1", "CLOSED_TARGET_2", "CLOSED_TARGET_3", "CLOSED_STOP", "CLOSED_INVALIDATED", "CLOSED_SESSION", "CLOSED_EXPIRY", "CANCELLED", "BLOCKED"})
TERMINAL_PAPER_TRADE_LIFECYCLE_STATES = frozenset({"CLOSED_TARGET_1", "CLOSED_TARGET_2", "CLOSED_TARGET_3", "CLOSED_STOP", "CLOSED_INVALIDATED", "CLOSED_SESSION", "CLOSED_EXPIRY", "CANCELLED", "BLOCKED"})
_NEXT = {"PLANNED": {"WAITING_FOR_ENTRY", "CANCELLED", "BLOCKED"}, "WAITING_FOR_ENTRY": {"OPEN", "CANCELLED", "CLOSED_INVALIDATED", "CLOSED_SESSION", "CLOSED_EXPIRY", "BLOCKED"}, "OPEN": {"PARTIALLY_EXITED", "CLOSED_TARGET_1", "CLOSED_TARGET_2", "CLOSED_TARGET_3", "CLOSED_STOP", "CLOSED_INVALIDATED", "CLOSED_SESSION", "CLOSED_EXPIRY", "CANCELLED", "BLOCKED"}, "PARTIALLY_EXITED": {"PARTIALLY_EXITED", "CLOSED_TARGET_2", "CLOSED_TARGET_3", "CLOSED_STOP", "CLOSED_INVALIDATED", "CLOSED_SESSION", "CLOSED_EXPIRY", "CANCELLED", "BLOCKED"}}
_TARGETS = {"CLOSED_TARGET_1": "T1", "CLOSED_TARGET_2": "T2", "CLOSED_TARGET_3": "T3"}

def _text(value: Any, name: str) -> str:
    if type(value) is not str or not (value := value.strip()): raise ValueError(name)
    return value
def _aware(value: Any, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None: raise ValueError(name)
    return value
def _freeze(value: Any) -> Any:
    if value is None or type(value) in (bool, int, str): return value
    if type(value) is float: return value
    if isinstance(value, Mapping): return MappingProxyType(dict(sorted((_text(k, "metadata key"), _freeze(v)) for k,v in value.items())))
    if type(value) in (tuple,list): return tuple(_freeze(v) for v in value)
    raise ValueError("metadata")
def _plain(value: Any) -> Any:
    if isinstance(value, Mapping): return {k:_plain(value[k]) for k in sorted(value)}
    if isinstance(value, tuple): return [_plain(v) for v in value]
    return value

def is_legal_paper_trade_lifecycle_transition(previous_state: str, next_state: str) -> bool:
    if previous_state not in CANONICAL_PAPER_TRADE_LIFECYCLE_STATES or next_state not in CANONICAL_PAPER_TRADE_LIFECYCLE_STATES:
        raise ValueError("canonical lifecycle state required")
    return next_state in _NEXT.get(previous_state, set())

@dataclass(frozen=True, slots=True)
class PaperTradeLifecycleStateV1:
    lifecycle_state_id: str
    trade_plan_id: str
    integrated_trade_plan_result_id: str
    lifecycle_policy_id: str
    current_state: str
    lifecycle_created_at: datetime
    previous_state: str | None = None
    transition_sequence: int = 0
    last_transition_code: str = "INITIAL"
    last_observation_id: str | None = None
    last_observation_timestamp: datetime | None = None
    waiting_for_entry_at: datetime | None = None
    opened_at: datetime | None = None
    partially_exited_at: datetime | None = None
    closed_at: datetime | None = None
    cancelled_at: datetime | None = None
    blocked_at: datetime | None = None
    terminal_reason: str | None = None
    terminal_target: str | None = None
    is_terminal: bool = False
    blockers: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"
    def __post_init__(self) -> None:
        for name in ("lifecycle_state_id","trade_plan_id","integrated_trade_plan_result_id","lifecycle_policy_id","current_state","last_transition_code"):
            object.__setattr__(self,name,_text(getattr(self,name),name))
        if self.current_state not in CANONICAL_PAPER_TRADE_LIFECYCLE_STATES: raise ValueError("current_state")
        _aware(self.lifecycle_created_at,"lifecycle_created_at")
        if self.previous_state is None:
            if self.current_state != "PLANNED" or self.transition_sequence != 0: raise ValueError("initial transition")
        else:
            if self.previous_state not in CANONICAL_PAPER_TRADE_LIFECYCLE_STATES or type(self.transition_sequence) is not int or isinstance(self.transition_sequence,bool) or self.transition_sequence <= 0 or not is_legal_paper_trade_lifecycle_transition(self.previous_state,self.current_state): raise ValueError("transition")
        if type(self.transition_sequence) is not int or isinstance(self.transition_sequence,bool) or self.transition_sequence < 0: raise ValueError("transition_sequence")
        if (self.last_observation_id is None) != (self.last_observation_timestamp is None): raise ValueError("observation coherence")
        if self.last_observation_id is not None: _text(self.last_observation_id,"last_observation_id"); _aware(self.last_observation_timestamp,"last_observation_timestamp")
        for name in ("waiting_for_entry_at","opened_at","partially_exited_at","closed_at","cancelled_at","blocked_at"):
            value=getattr(self,name)
            if value is not None: _aware(value,name)
        terminal = self.current_state in TERMINAL_PAPER_TRADE_LIFECYCLE_STATES
        if type(self.is_terminal) is not bool or self.is_terminal != terminal: raise ValueError("is_terminal")
        if terminal and self.terminal_reason is None: raise ValueError("terminal_reason")
        if not terminal and (self.terminal_reason is not None or self.terminal_target is not None or self.closed_at is not None): raise ValueError("nonterminal evidence")
        if self.terminal_reason is not None: object.__setattr__(self,"terminal_reason",_text(self.terminal_reason,"terminal_reason"))
        expected_target=_TARGETS.get(self.current_state)
        if expected_target is not None and self.terminal_target != expected_target: raise ValueError("terminal_target")
        if expected_target is None and self.terminal_target is not None: raise ValueError("terminal_target")
        if self.current_state.startswith("CLOSED_") and self.closed_at is None: raise ValueError("closed_at")
        if self.current_state == "CANCELLED" and self.cancelled_at is None: raise ValueError("cancelled_at")
        if self.current_state == "BLOCKED" and (self.blocked_at is None or not self.blockers): raise ValueError("blocked")
        for name in ("blockers","decision_reasons","warnings"):
            value=getattr(self,name)
            if not isinstance(value,tuple): raise TypeError(name)
            object.__setattr__(self,name,tuple(dict.fromkeys(_text(item,name) for item in value)))
        if self.current_state != "BLOCKED" and self.blockers: raise ValueError("blockers")
        object.__setattr__(self,"metadata",_freeze(self.metadata))
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.schema_version != "1.0": raise ValueError("paper")
    def to_dict(self) -> dict[str,Any]:
        result={name:getattr(self,name) for name in self.__dataclass_fields__}
        for name in ("lifecycle_created_at","last_observation_timestamp","waiting_for_entry_at","opened_at","partially_exited_at","closed_at","cancelled_at","blocked_at"):
            if result[name] is not None: result[name]=result[name].isoformat()
        for name in ("blockers","decision_reasons","warnings"): result[name]=list(result[name])
        result["metadata"]=_plain(self.metadata); return result
    def to_json(self) -> str: return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
    def semantic_dict(self) -> dict[str,Any]:
        result=self.to_dict()
        for name in ("lifecycle_state_id","lifecycle_created_at","waiting_for_entry_at","opened_at","partially_exited_at","closed_at","cancelled_at","blocked_at","last_observation_timestamp"): result.pop(name)
        return result

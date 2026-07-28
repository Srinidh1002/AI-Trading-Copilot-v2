"""Typed, non-executable canonical outcome for P3-5 risk validation."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from .final_decision_v1 import FinalDecisionV1
from .trade_plan_v1 import TradePlanV1
from .position_size_result_v1 import PositionSizeResultV1

_STATUSES={"RISK_APPROVED","NO_ACTION","BLOCKED","INSUFFICIENT_CAPITAL","INVALID_RISK","LIMIT_EXCEEDED","FAILED"}

@dataclass(frozen=True, slots=True)
class CanonicalRiskResultV1:
    result_id:str; created_at:datetime; snapshot_id:str; analysis_id:str|None; decision_id:str; trade_plan_result_id:str|None; sizing_result_id:str|None; decision:FinalDecisionV1; trade_plan:TradePlanV1|None; sizing_result:PositionSizeResultV1|None; risk_status:str; schema_version:str="canonical_risk_result.v1"; blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if self.schema_version!="canonical_risk_result.v1" or self.risk_status not in _STATUSES or not isinstance(self.created_at,datetime) or self.created_at.tzinfo is None: raise ValueError("Invalid canonical risk schema, status, or timestamp.")
        for name in ("result_id","snapshot_id","decision_id"):
            if not isinstance(getattr(self,name),str) or not getattr(self,name).strip(): raise ValueError(f"{name} is required.")
        if not isinstance(self.decision,FinalDecisionV1) or (self.decision.snapshot_id,self.decision.decision_id)!=(self.snapshot_id,self.decision_id): raise ValueError("Decision identity is inconsistent.")
        if self.analysis_id is not None and (not isinstance(self.analysis_id,str) or not self.analysis_id): raise ValueError("analysis_id must be non-empty when supplied.")
        if self.trade_plan is not None:
            if not isinstance(self.trade_plan,TradePlanV1) or (self.trade_plan.snapshot_id,self.trade_plan.decision_id)!=(self.snapshot_id,self.decision_id) or self.trade_plan.analysis_id!=self.analysis_id: raise ValueError("Trade-plan identity is inconsistent.")
        if self.sizing_result is not None:
            s=self.sizing_result
            if not isinstance(s,PositionSizeResultV1) or (s.snapshot_id,s.decision_id)!=(self.snapshot_id,self.decision_id): raise ValueError("Sizing identity is inconsistent.")
            if self.trade_plan is not None and (s.trade_plan_id!=self.trade_plan.trade_plan_id or s.selection_id!=self.trade_plan.selection_id or s.contract_id!=self.trade_plan.contract_id): raise ValueError("Sizing and trade-plan identity is inconsistent.")
            if self.sizing_result_id!=s.sizing_result_id: raise ValueError("sizing_result_id is inconsistent.")
            if s.execution_eligible: raise ValueError("Execution eligibility is prohibited.")
        blockers=tuple(self.blockers); warnings=tuple(self.warnings)
        if any(not isinstance(x,str) or not x for x in blockers+warnings): raise ValueError("Blockers and warnings must be non-empty strings.")
        if self.risk_status=="RISK_APPROVED":
            if self.trade_plan is None or self.trade_plan.plan_status!="READY_FOR_RISK" or self.sizing_result is None or self.sizing_result.sizing_status!="APPROVED" or not self.sizing_result.risk_approved or not self.sizing_result.paper_preparation_eligible or blockers: raise ValueError("Invalid approved risk result.")
        elif self.risk_status=="NO_ACTION":
            if self.decision.action in {"BUY","SELL"} or self.sizing_result is not None or self.trade_plan is not None: raise ValueError("Invalid no-action risk result.")
        elif self.risk_status in {"BLOCKED","INSUFFICIENT_CAPITAL","INVALID_RISK","LIMIT_EXCEEDED","FAILED"}:
            if not blockers: raise ValueError("Non-approved risk result requires blockers.")
            if self.sizing_result is not None:
                if self.sizing_result.risk_approved or self.sizing_result.paper_preparation_eligible: raise ValueError("Non-approved sizing cannot be eligible.")
                expected={"INSUFFICIENT_CAPITAL":"INSUFFICIENT_CAPITAL","INVALID_RISK":"INVALID_RISK","LIMIT_EXCEEDED":"LIMIT_EXCEEDED"}.get(self.risk_status)
                if expected and self.sizing_result.sizing_status!=expected: raise ValueError("Sizing status does not match risk status.")
        try: json.dumps(self.metadata,sort_keys=True,allow_nan=False)
        except (TypeError,ValueError) as exc: raise ValueError("metadata must be safe JSON.") from exc
        object.__setattr__(self,"blockers",blockers); object.__setattr__(self,"warnings",warnings); object.__setattr__(self,"metadata",dict(self.metadata))
    def to_dict(self):
        return {"schema_version":self.schema_version,"result_id":self.result_id,"created_at":self.created_at.isoformat(),"snapshot_id":self.snapshot_id,"analysis_id":self.analysis_id,"decision_id":self.decision_id,"trade_plan_result_id":self.trade_plan_result_id,"sizing_result_id":self.sizing_result_id,"decision":self.decision.to_dict(),"trade_plan":self.trade_plan.to_dict() if self.trade_plan else None,"sizing_result":self.sizing_result.to_dict() if self.sizing_result else None,"risk_status":self.risk_status,"blockers":list(self.blockers),"warnings":list(self.warnings),"metadata":dict(sorted(self.metadata.items()))}
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
    def semantic_dict(self):
        value=self.to_dict(); value.pop("result_id"); value.pop("created_at"); return value

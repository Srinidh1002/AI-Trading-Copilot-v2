import json
from dataclasses import dataclass,field
from datetime import datetime
from typing import Any,Mapping
@dataclass(frozen=True,slots=True)
class CanonicalTradePlanResultV1:
    result_id:str; created_at:datetime; snapshot_id:str; analysis_id:str|None; decision_id:str; decision:Any; selected_contract:Any|None; trade_plan:Any|None; result_status:str; schema_version:str="canonical_trade_plan_result.v1"; blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if self.schema_version!="canonical_trade_plan_result.v1" or not self.result_id or self.created_at.tzinfo is None or not self.snapshot_id or not self.decision_id or getattr(self.decision,"snapshot_id",None)!=self.snapshot_id or getattr(self.decision,"decision_id",None)!=self.decision_id or self.result_status not in {"PLAN_CREATED","NO_ACTION","BLOCKED","INSUFFICIENT_DATA","FAILED"}: raise ValueError("Invalid canonical trade-plan result.")
        if self.result_status=="PLAN_CREATED" and (self.selected_contract is None or not self.selected_contract.selection_valid or self.trade_plan is None or self.trade_plan.plan_status!="READY_FOR_RISK" or self.blockers): raise ValueError("Invalid created plan result.")
        if self.result_status in {"BLOCKED","INSUFFICIENT_DATA","FAILED"} and not self.blockers: raise ValueError("Blocked result requires blockers.")
        if self.result_status=="NO_ACTION" and self.trade_plan is not None: raise ValueError("No-action result cannot have a plan.")
        object.__setattr__(self,"metadata",dict(self.metadata)); object.__setattr__(self,"blockers",tuple(self.blockers)); object.__setattr__(self,"warnings",tuple(self.warnings))
    def to_dict(self): return {"schema_version":self.schema_version,"result_id":self.result_id,"created_at":self.created_at.isoformat(),"snapshot_id":self.snapshot_id,"analysis_id":self.analysis_id,"decision_id":self.decision_id,"decision":self.decision.to_dict(),"selected_contract":self.selected_contract.to_dict() if self.selected_contract else None,"trade_plan":self.trade_plan.to_dict() if self.trade_plan else None,"result_status":self.result_status,"blockers":list(self.blockers),"warnings":list(self.warnings),"metadata":dict(self.metadata)}
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
    def semantic_dict(self): d=self.to_dict(); d.pop("result_id"); d.pop("created_at"); return d

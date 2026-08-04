from __future__ import annotations
import json,math
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from dataclasses import dataclass,field
from datetime import date,datetime
from typing import Any,Mapping
@dataclass(frozen=True,slots=True)
class TradePlanV1:
    trade_plan_id:str; created_at:datetime; snapshot_id:str; analysis_id:str|None; decision_id:str; selection_id:str|None; contract_id:str|None; underlying_symbol:str; exchange:str; action:str; option_type:str|None; trading_symbol:str|None; expiry_date:date|None; strike:float|None; lot_size:int|None; entry_reference_price:float|None; entry_price_source:str|None; stop_loss_price:float|None; target_price:float|None; stop_loss_source:str|None; target_source:str|None; valid_from:datetime; valid_until:datetime; plan_status:str; paper_preparation_eligible:bool; schema_version:str="trade_plan.v1"; quantity:None=None; lots:None=None; capital_required:None=None; maximum_loss:None=None; execution_eligible:bool=False; blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if self.schema_version!="trade_plan.v1" or not all((self.trade_plan_id,self.snapshot_id,self.decision_id)) or self.created_at.tzinfo is None or self.valid_from.tzinfo is None or self.valid_until.tzinfo is None or self.plan_status not in {"READY_FOR_RISK","BLOCKED","INSUFFICIENT_DATA","EXPIRED","INVALID"} or self.execution_eligible or any(x is not None for x in (self.quantity,self.lots,self.capital_required,self.maximum_loss)): raise ValueError("Invalid risk-pending trade plan.")
        if (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES: raise ValueError("Invalid plan identity.")
        if self.plan_status=="READY_FOR_RISK":
            if self.valid_until<=self.valid_from or not all((self.selection_id,self.contract_id,self.trading_symbol,self.expiry_date is not None,self.strike is not None,self.lot_size is not None)) or self.action not in {"BUY","SELL"} or self.option_type not in {"CALL","PUT"} or (self.action=="BUY" and self.option_type!="CALL") or (self.action=="SELL" and self.option_type!="PUT") or self.blockers or not self.paper_preparation_eligible: raise ValueError("Invalid ready trade plan.")
        elif not self.blockers or self.paper_preparation_eligible: raise ValueError("Invalid non-ready trade plan.")
        ids=(self.selection_id,self.contract_id,self.trading_symbol,self.expiry_date,self.strike,self.lot_size)
        if self.plan_status!="READY_FOR_RISK" and any(x is not None for x in ids) and not all(x is not None for x in ids): raise ValueError("Partial contract identity is invalid.")
        if self.strike is not None and (not math.isfinite(self.strike) or self.strike<=0): raise ValueError("Invalid strike.")
        if self.lot_size is not None and (isinstance(self.lot_size,bool) or not isinstance(self.lot_size,int) or self.lot_size<=0): raise ValueError("Invalid lot size.")
        for x in (self.entry_reference_price,self.stop_loss_price,self.target_price):
            if x is not None and (not math.isfinite(x) or x<0): raise ValueError("Invalid plan price.")
        try: json.dumps(self.metadata,sort_keys=True,allow_nan=False)
        except (TypeError,ValueError) as exc: raise ValueError("metadata must be safe JSON.") from exc
        object.__setattr__(self,"metadata",dict(self.metadata)); object.__setattr__(self,"blockers",tuple(self.blockers)); object.__setattr__(self,"warnings",tuple(self.warnings))
    def to_dict(self): return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),(date,datetime)) else list(getattr(self,n)) if n in {"blockers","warnings"} else dict(getattr(self,n)) if n=="metadata" else getattr(self,n)) for n in self.__dataclass_fields__}
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
    def semantic_dict(self): d=self.to_dict(); d.pop("trade_plan_id"); d.pop("created_at"); return d

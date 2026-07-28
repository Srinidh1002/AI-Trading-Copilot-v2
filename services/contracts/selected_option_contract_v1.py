from __future__ import annotations
import json,math
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from dataclasses import dataclass,field
from datetime import date,datetime
from typing import Any,Mapping
@dataclass(frozen=True,slots=True)
class SelectedOptionContractV1:
    selection_id:str; selected_at:datetime; snapshot_id:str; decision_id:str; universe_id:str|None; contract_id:str|None; underlying_symbol:str; exchange:str; action:str; option_type:str|None; trading_symbol:str|None; instrument_token:str|None; expiry_date:date|None; strike:float|None; lot_size:int|None; reference_spot_price:float|None; reference_option_price:float|None; reference_price_source:str; expiry_selection_policy:str; strike_selection_policy:str; selection_valid:bool; blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); metadata:Mapping[str,Any]=field(default_factory=dict); schema_version:str="selected_option_contract.v1"
    def __post_init__(self):
        if self.schema_version!="selected_option_contract.v1" or not self.selection_id or not self.snapshot_id or not self.decision_id or self.selected_at.tzinfo is None or (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES or (self.selection_valid and self.blockers) or (not self.selection_valid and not self.blockers): raise ValueError("Invalid selected contract.")
        if self.option_type is not None and self.option_type not in {"CALL","PUT"}: raise ValueError("Invalid option type.")
        if self.selection_valid:
            if not all((self.universe_id,self.contract_id,self.trading_symbol,self.expiry_date is not None,self.strike is not None,self.lot_size is not None,self.option_type in {"CALL","PUT"})): raise ValueError("Valid selection requires complete contract identity.")
            if self.action not in {"BUY","SELL"} or (self.action=="BUY" and self.option_type!="CALL") or (self.action=="SELL" and self.option_type!="PUT"): raise ValueError("Invalid action/direction.")
        else:
            identities=(self.universe_id,self.contract_id,self.trading_symbol,self.expiry_date,self.strike,self.lot_size)
            if any(value is not None for value in identities) and not all(value is not None for value in identities): raise ValueError("Blocked selection cannot contain partial contract identity.")
        for value in (self.strike,self.reference_spot_price,self.reference_option_price):
            if value is not None and (not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0): raise ValueError("Invalid price or strike.")
        if self.lot_size is not None and (isinstance(self.lot_size,bool) or not isinstance(self.lot_size,int) or self.lot_size<=0): raise ValueError("Invalid lot size.")
        if self.reference_price_source not in {"MID","ASK","LAST","BID","UNAVAILABLE"} or self.expiry_selection_policy not in {"EARLIEST_ELIGIBLE","EXPLICIT_EXPIRY_ONLY"} or self.strike_selection_policy not in {"NEAREST_ATM","EXPLICIT_STRIKE_ONLY"}: raise ValueError("Invalid selection policy.")
        try: json.dumps(self.metadata,sort_keys=True,allow_nan=False)
        except (TypeError,ValueError) as exc: raise ValueError("metadata must be safe JSON data.") from exc
        object.__setattr__(self,"metadata",dict(self.metadata)); object.__setattr__(self,"blockers",tuple(self.blockers)); object.__setattr__(self,"warnings",tuple(self.warnings))
    def to_dict(self): return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),(date,datetime)) else list(getattr(self,n)) if n in {"blockers","warnings"} else dict(getattr(self,n)) if n=="metadata" else getattr(self,n)) for n in self.__dataclass_fields__}
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
    def semantic_dict(self):
        d=self.to_dict(); d.pop("selection_id"); d.pop("selected_at"); return d

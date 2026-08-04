from __future__ import annotations
import json,math
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from dataclasses import dataclass,field
from datetime import datetime
from typing import Any,Mapping
from .option_contract_v1 import OptionContractV1
@dataclass(frozen=True,slots=True)
class OptionContractUniverseV1:
    universe_id:str; underlying_symbol:str; exchange:str; captured_at:datetime; spot_price:float; contracts:tuple[OptionContractV1,...]; source_name:str; trusted:bool; schema_version:str="option_contract_universe.v1"; warnings:tuple[str,...]=(); metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if self.schema_version!="option_contract_universe.v1" or not self.universe_id or (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES or self.captured_at.tzinfo is None or not math.isfinite(self.spot_price) or self.spot_price<=0: raise ValueError("Invalid option universe.")
        if not all(isinstance(c,OptionContractV1) for c in self.contracts) or len({c.contract_id for c in self.contracts})!=len(self.contracts) or any((c.underlying_symbol,c.exchange)!=(self.underlying_symbol,self.exchange) for c in self.contracts): raise ValueError("Universe contract identity mismatch.")
        try: json.dumps(self.metadata,sort_keys=True,allow_nan=False)
        except (TypeError,ValueError) as exc: raise ValueError("metadata must be safe JSON data.") from exc
        object.__setattr__(self,"contracts",tuple(sorted(tuple(self.contracts),key=lambda c:(c.expiry_date,c.strike,c.contract_id)))); object.__setattr__(self,"metadata",dict(self.metadata)); object.__setattr__(self,"warnings",tuple(self.warnings))
    def to_dict(self): return {"schema_version":self.schema_version,"universe_id":self.universe_id,"underlying_symbol":self.underlying_symbol,"exchange":self.exchange,"captured_at":self.captured_at.isoformat(),"spot_price":self.spot_price,"contracts":[c.to_dict() for c in self.contracts],"source_name":self.source_name,"trusted":self.trusted,"warnings":list(self.warnings),"metadata":dict(self.metadata)}
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
    def semantic_dict(self): return self.to_dict()

from __future__ import annotations
import json,math
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from dataclasses import dataclass,field
from datetime import date,datetime
from typing import Any,Mapping
@dataclass(frozen=True,slots=True)
class OptionContractV1:
    contract_id:str; underlying_symbol:str; exchange:str; trading_symbol:str; option_type:str; strike:float; expiry_date:date; lot_size:int; market_timestamp:datetime; schema_version:str="option_contract.v1"; instrument_token:str|None=None; tick_size:float|None=None; last_price:float|None=None; bid_price:float|None=None; ask_price:float|None=None; open_interest:float|None=None; volume:float|None=None; implied_volatility:float|None=None; tradable:bool=True; metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if self.schema_version!="option_contract.v1" or not self.contract_id or not self.trading_symbol or (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES or self.option_type not in {"CALL","PUT"} or isinstance(self.lot_size,bool) or not isinstance(self.lot_size,int) or self.lot_size<=0 or self.market_timestamp.tzinfo is None: raise ValueError("Invalid option contract.")
        for x in (self.strike,self.tick_size,self.last_price,self.bid_price,self.ask_price,self.open_interest,self.volume,self.implied_volatility):
            if x is not None and (not isinstance(x,(int,float)) or not math.isfinite(x) or x<0): raise ValueError("Contract numeric values must be finite and non-negative.")
        if self.strike<=0: raise ValueError("strike must be positive.")
        try: json.dumps(self.metadata, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError) as exc: raise ValueError("metadata must be safe JSON data.") from exc
        object.__setattr__(self,"metadata",dict(self.metadata))
    def to_dict(self): return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),(date,datetime)) else dict(getattr(self,n)) if n=="metadata" else getattr(self,n)) for n in self.__dataclass_fields__}
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
    def semantic_dict(self): return self.to_dict()

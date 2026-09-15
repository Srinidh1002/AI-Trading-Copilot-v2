"""Supplied-evidence-only pre-market context; never authorizes a trade."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from services.contracts.canonical_directional_policy_v1 import _aware
@dataclass(frozen=True,slots=True)
class PreMarketBrainV1:
 market_date:date; symbol:str; exchange:str; evaluated_at:datetime; session_open:bool; previous_close:float|None=None; prior_oi_snapshot_id:str|None=None; india_vix:float|None=None; external_status:str="UNAVAILABLE"; official_live_count:int=0; broker_execution_authorized:bool=False; schema_version:str="pre-market-brain.v1"
 def __post_init__(self):
  if self.symbol.upper() not in {"NIFTY","SENSEX"} or self.exchange.upper() not in {"NSE","BSE"}: raise ValueError("identity")
  if self.session_open: raise ValueError("pre-market context cannot represent live session")
  if self.official_live_count or self.broker_execution_authorized: raise ValueError("pre-market context cannot authorize count or execution")
  object.__setattr__(self,"evaluated_at",_aware(self.evaluated_at,"evaluated_at"))

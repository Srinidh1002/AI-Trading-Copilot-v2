"""Fixed, provider-free Task 2 decision-certification inputs."""
from dataclasses import dataclass
from datetime import datetime

_MARKETS={"NIFTY":("NIFTY","NSE"),"SENSEX":("SENSEX","BSE")}
_PROFILES={"ELIGIBLE_BULLISH","ELIGIBLE_BEARISH","VALID_WAIT","UNAVAILABLE_CHILD","CONFLICTING_CHILD","REQUIRED_EVIDENCE_MISSING","OPTIONAL_EXTERNAL_UNAVAILABLE","REGIME_BLOCKED"}
def _text(value,name):
 if type(value) is not str or not value.strip():raise ValueError(name)
 return value.strip()
def _aware(value,name):
 if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:raise ValueError(name)
 return value
@dataclass(frozen=True,slots=True)
class Task2MarketFixtureV1:
 fixture_profile_id:str;underlying_symbol:str;exchange:str;parent_cycle_id:str;observation_id:str;candidate_id:str;fixed_evaluated_at:datetime;candidate_direction:str;candidate_eligibility:str;candidate_confidence:float;candidate_score:float;regime_suitability:str|None;evidence_profile:str;child_terminal_profile:str;controlled_blockers:tuple[str,...]=();controlled_warnings:tuple[str,...]=();controlled_contradictions:tuple[str,...]=();expected_action:str="WAIT";expected_terminal_status:str="COMPLETED";expected_ledger_status:str="READY";build_fourteen_pillars:bool=True
 def __post_init__(self):
  for n in ("fixture_profile_id","parent_cycle_id","observation_id","candidate_id","evidence_profile","child_terminal_profile"):object.__setattr__(self,n,_text(getattr(self,n),n))
  symbol=_text(self.underlying_symbol,"underlying_symbol").upper();exchange=_text(self.exchange,"exchange").upper()
  if _MARKETS.get(symbol)!=(symbol,exchange):raise ValueError("market identity")
  object.__setattr__(self,"underlying_symbol",symbol);object.__setattr__(self,"exchange",exchange);_aware(self.fixed_evaluated_at,"fixed_evaluated_at")
  if self.fixture_profile_id not in _PROFILES:raise ValueError("fixture_profile_id")
  if self.expected_action not in {"CALL","PUT","WAIT","UNAVAILABLE"} or self.expected_terminal_status not in {"COMPLETED","FAILED","UNAVAILABLE"}:raise ValueError("expected outcome")
  for n in ("candidate_confidence","candidate_score"):
   value=getattr(self,n)
   if type(value) not in (int,float) or not 0<=value<=100:raise ValueError(n)
@dataclass(frozen=True,slots=True)
class Task2TwoMarketFixtureV1:
 scenario_id:str;parent_cycle_id:str;fixed_evaluated_at:datetime;nifty:Task2MarketFixtureV1;sensex:Task2MarketFixtureV1;expected_selected_market:str="NONE";expected_parent_action:str="NO_TRADE";expected_parent_status:str="NO_TRADE";expected_invariant_status:str="VALID"
 def __post_init__(self):
  for n in ("scenario_id","parent_cycle_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  _aware(self.fixed_evaluated_at,"fixed_evaluated_at")
  if type(self.nifty) is not Task2MarketFixtureV1 or type(self.sensex) is not Task2MarketFixtureV1:raise TypeError("market fixtures")
  if (self.nifty.underlying_symbol,self.nifty.exchange)!=("NIFTY","NSE") or (self.sensex.underlying_symbol,self.sensex.exchange)!=("SENSEX","BSE"):raise ValueError("exact markets")
  if self.nifty.parent_cycle_id!=self.parent_cycle_id or self.sensex.parent_cycle_id!=self.parent_cycle_id:raise ValueError("parent cycle")
  if len({self.nifty.candidate_id,self.sensex.candidate_id,self.nifty.observation_id,self.sensex.observation_id})!=4:raise ValueError("market identities")

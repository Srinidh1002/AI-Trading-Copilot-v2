"""Paper-only technical evidence for one canonical timeframe."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import math
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from .technical_indicator_value_v1 import TechnicalIndicatorValueV1

_TIMEFRAMES={"5m","15m","1h","1d"};_CATEGORIES={"TREND","MOMENTUM","VOLATILITY","VOLUME","LEVELS","PATTERNS"}
_BIASES={"BULLISH","BEARISH","NEUTRAL","UNAVAILABLE"};_MOMENTUM=_BIASES|{"OVERBOUGHT","OVERSOLD"};_VOL={"EXPANDING","CONTRACTING","NORMAL","HIGH","LOW","UNAVAILABLE"};_VOLUME={"SUPPORTIVE","WEAK","NEUTRAL","UNAVAILABLE"};_LEVEL={"ABOVE_RESISTANCE","BELOW_SUPPORT","NEAR_RESISTANCE","NEAR_SUPPORT","INSIDE_RANGE","UNAVAILABLE"};_PATTERN={"BULLISH","BEARISH","NEUTRAL","NONE","UNAVAILABLE"}

@dataclass(frozen=True,slots=True)
class TimeframeTechnicalEvidenceV1:
 timeframe_technical_evidence_id:str;created_at:datetime;underlying_symbol:str;exchange:str;timeframe:str;timeframe_evidence_id:str;indicators:tuple[TechnicalIndicatorValueV1,...];category_biases:tuple[tuple[str,str],...];category_strengths:tuple[tuple[str,float],...];blockers:tuple[str,...]=();warnings:tuple[str,...]=();execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="timeframe_technical_evidence.v1"
 trend_bias:str="UNAVAILABLE";momentum_bias:str="UNAVAILABLE";volatility_state:str="UNAVAILABLE";volume_state:str="UNAVAILABLE";level_state:str="UNAVAILABLE";pattern_state:str="UNAVAILABLE"
 trend_strength:float=0.;momentum_strength:float=0.;volatility_strength:float=0.;volume_strength:float=0.;level_strength:float=0.;pattern_strength:float=0.
 bullish_evidence_count:int=0;bearish_evidence_count:int=0;neutral_evidence_count:int=0;valid_indicator_count:int=0;unavailable_indicator_count:int=0
 def __post_init__(self):
  biases,strengths,indicators=tuple(self.category_biases),tuple(self.category_strengths),tuple(self.indicators)
  if (not self.timeframe_technical_evidence_id or not self.timeframe_evidence_id or not isinstance(self.created_at,datetime) or not self.created_at.tzinfo or (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES or self.timeframe not in _TIMEFRAMES or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="timeframe_technical_evidence.v1"):raise ValueError("Invalid timeframe technical evidence.")
  if (any(not isinstance(x,TechnicalIndicatorValueV1) or x.timeframe!=self.timeframe for x in indicators) or len({x.indicator_name for x in indicators})!=len(indicators) or {k for k,_ in biases}!=_CATEGORIES or {k for k,_ in strengths}!=_CATEGORIES or len(biases)!=6 or len(strengths)!=6 or any(v not in _BIASES for _,v in biases) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for _,v in strengths)):raise ValueError("Invalid technical categories.")
  states=(self.trend_bias,self.momentum_bias,self.volatility_state,self.volume_state,self.level_state,self.pattern_state);allowed=(_BIASES,_MOMENTUM,_VOL,_VOLUME,_LEVEL,_PATTERN);strengths2=(self.trend_strength,self.momentum_strength,self.volatility_strength,self.volume_strength,self.level_strength,self.pattern_strength)
  if any(v not in a for v,a in zip(states,allowed)) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in strengths2) or any(state=="UNAVAILABLE" and strength!=0 for state,strength in zip(states,strengths2)):raise ValueError("Invalid category state.")
  valid=sum(x.status=="VALID" for x in indicators);unavailable=len(indicators)-valid
  if not indicators and any((self.valid_indicator_count,self.unavailable_indicator_count,self.bullish_evidence_count,self.bearish_evidence_count,self.neutral_evidence_count)):raise ValueError("Empty indicators cannot have counts.")
  if indicators and self.valid_indicator_count==0 and self.unavailable_indicator_count==0:object.__setattr__(self,"valid_indicator_count",valid);object.__setattr__(self,"unavailable_indicator_count",unavailable)
  if self.valid_indicator_count<0 or self.unavailable_indicator_count<0 or self.valid_indicator_count+self.unavailable_indicator_count!=len(indicators) or any(not isinstance(v,int) or isinstance(v,bool) or v<0 for v in (self.bullish_evidence_count,self.bearish_evidence_count,self.neutral_evidence_count)) or self.bullish_evidence_count+self.bearish_evidence_count+self.neutral_evidence_count>self.valid_indicator_count:raise ValueError("Invalid indicator counts.")
  for n,v in (("indicators",indicators),("category_biases",biases),("category_strengths",strengths),("blockers",tuple(self.blockers)),("warnings",tuple(self.warnings))):object.__setattr__(self,n,v)
 def to_dict(self):
  return {n:([x.to_dict() for x in self.indicators] if n=="indicators" else [[k,v] for k,v in getattr(self,n)] if n in {"category_biases","category_strengths"} else list(getattr(self,n)) if n in {"blockers","warnings"} else self.created_at.isoformat() if n=="created_at" else getattr(self,n)) for n in self.__dataclass_fields__}

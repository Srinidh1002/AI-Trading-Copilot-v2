from dataclasses import dataclass
_T=("5m","15m","1h","1d")
@dataclass(frozen=True,slots=True)
class MultiTimeframePolicyV1:
 policy_name:str;required_timeframes:tuple[str,...];anchor_timeframe:str;minimum_complete_candles_by_timeframe:tuple[tuple[str,int],...];maximum_alignment_gap_seconds_by_timeframe:tuple[tuple[str,float],...];incomplete_latest_candle_behavior:str;missing_timeframe_behavior:str;stale_timeframe_behavior:str;insufficient_history_behavior:str;execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="multi_timeframe_policy.v1"
 def __post_init__(self):
  if not self.policy_name or self.required_timeframes!=_T or self.anchor_timeframe!="5m" or tuple(k for k,_ in self.minimum_complete_candles_by_timeframe)!=_T or tuple(k for k,_ in self.maximum_alignment_gap_seconds_by_timeframe)!=_T or any(v<=0 for _,v in self.minimum_complete_candles_by_timeframe) or any(v<0 for _,v in self.maximum_alignment_gap_seconds_by_timeframe) or self.incomplete_latest_candle_behavior not in {"WARN","BLOCK","ALLOW"} or any(v not in {"BLOCK","WARN"} for v in (self.missing_timeframe_behavior,self.stale_timeframe_behavior,self.insufficient_history_behavior)) or self.execution_mode!="PAPER" or self.live_execution_eligible is not False:raise ValueError("Invalid multi-timeframe policy.")
DEFAULT_MULTI_TIMEFRAME_POLICY=MultiTimeframePolicyV1("INITIAL_CANONICAL_MTF_POLICY",_T,"5m",(("5m",60),("15m",60),("1h",50),("1d",50)),(("5m",300),("15m",900),("1h",3600),("1d",86400)),"WARN","BLOCK","BLOCK","BLOCK")

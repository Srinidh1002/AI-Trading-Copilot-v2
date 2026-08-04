from dataclasses import dataclass
_TF=("1m","3m","5m","15m","30m","1h","1d")
@dataclass(frozen=True,slots=True)
class MarketDataFreshnessPolicyV1:
 policy_name:str;quote_max_age_seconds:float;cache_max_age_seconds:float;future_tolerance_seconds:float;provider_clock_skew_tolerance_seconds:float;candle_max_age_by_timeframe:tuple[tuple[str,float],...];incomplete_candle_behavior:str;empty_series_behavior:str;provider_disagreement_warning_bps:float;provider_disagreement_block_bps:float;execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="market_data_freshness_policy.v1"
 def __post_init__(self):
  if not self.policy_name or tuple(k for k,_ in self.candle_max_age_by_timeframe)!=_TF or any(v<=0 for _,v in self.candle_max_age_by_timeframe) or any(v<0 for v in (self.future_tolerance_seconds,self.provider_clock_skew_tolerance_seconds)) or any(v<=0 for v in (self.quote_max_age_seconds,self.cache_max_age_seconds,self.provider_disagreement_warning_bps,self.provider_disagreement_block_bps)) or self.provider_disagreement_warning_bps>self.provider_disagreement_block_bps or self.incomplete_candle_behavior not in {"WARN","BLOCK","ALLOW"} or self.empty_series_behavior not in {"BLOCK","WARN"} or self.execution_mode!="PAPER" or self.live_execution_eligible is not False:raise ValueError("Invalid freshness policy.")
DEFAULT_MARKET_DATA_FRESHNESS_POLICY=MarketDataFreshnessPolicyV1("INITIAL_CANONICAL_POLICY",300,300,5,5,(("1m",120),("3m",360),("5m",600),("15m",1800),("30m",3600),("1h",7200),("1d",172800)),"WARN","BLOCK",10,50)

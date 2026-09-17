from __future__ import annotations
import json, math
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True,slots=True)
class IndiaVixRegimePolicyV1:
 policy_id:str="INDIA_VIX_COMPATIBILITY_POLICY_2026_08_03";effective_from:date=date(2026,8,3);low_upper_exclusive:float=13.;normal_upper_exclusive:float=18.;elevated_upper_exclusive:float=20.;high_upper_exclusive:float=28.;execution_modes:tuple[str,...]=( "PAPER","MANUAL_LIVE");source_basis:str="Repository compatibility approval: 13, 18, 20, 28";schema_version:str="india_vix_regime_policy.v1"
 def __post_init__(self):
  if not self.policy_id or self.effective_from!=date(2026,8,3) or self.execution_modes!=("PAPER","MANUAL_LIVE") or self.schema_version!="india_vix_regime_policy.v1":raise ValueError("invalid India VIX policy")
  if (self.low_upper_exclusive,self.normal_upper_exclusive,self.elevated_upper_exclusive,self.high_upper_exclusive)!=(13.,18.,20.,28.):raise ValueError("India VIX thresholds are immutable")
 def to_dict(self):return {"policy_id":self.policy_id,"effective_from":self.effective_from.isoformat(),"boundaries":{"LOW":"0 < value < 13","NORMAL":"13 <= value < 18","ELEVATED":"18 <= value < 20","HIGH":"20 <= value < 28","EXTREME":"value >= 28"},"execution_modes":list(self.execution_modes),"source_basis":self.source_basis,"schema_version":self.schema_version}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
DEFAULT_INDIA_VIX_REGIME_POLICY=IndiaVixRegimePolicyV1()
def classify_india_vix_regime(value,policy=DEFAULT_INDIA_VIX_REGIME_POLICY):
 if type(policy) is not IndiaVixRegimePolicyV1:raise TypeError("policy")
 if value is None or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(float(value)) or value<=0:return "UNAVAILABLE"
 value=float(value)
 return "LOW" if value<13 else "NORMAL" if value<18 else "ELEVATED" if value<20 else "HIGH" if value<28 else "EXTREME"

from dataclasses import dataclass
import math
@dataclass(frozen=True,slots=True)
class OptionSelectionPolicy:
    max_universe_age_seconds:float=300.; max_contract_age_seconds:float=300.; max_future_skew_seconds:float=5.; expiry_policy:str="EARLIEST_ELIGIBLE"; strike_policy:str="NEAREST_ATM"; reference_price_policy:str="BEST_AVAILABLE"; require_trusted_universe:bool=True
    def __post_init__(self):
        if self.expiry_policy not in {"EARLIEST_ELIGIBLE","EXPLICIT_EXPIRY_ONLY"} or self.strike_policy not in {"NEAREST_ATM","EXPLICIT_STRIKE_ONLY"} or self.reference_price_policy not in {"MID","ASK","LAST","BEST_AVAILABLE"}: raise ValueError("Unsupported selection policy.")
@dataclass(frozen=True,slots=True)
class TradePlanPolicy:
    validity_seconds:float=300.; require_entry_reference_price:bool=True; require_stop_loss:bool=False; require_target:bool=False
    def __post_init__(self):
        if not math.isfinite(self.validity_seconds) or self.validity_seconds<=0 or not all(isinstance(value,bool) for value in (self.require_entry_reference_price,self.require_stop_loss,self.require_target)): raise ValueError("Invalid trade plan policy.")

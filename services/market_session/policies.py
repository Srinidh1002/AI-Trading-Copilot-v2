from dataclasses import dataclass
from datetime import time
@dataclass(frozen=True,slots=True)
class MarketSessionPolicy:
    timezone:str="Asia/Kolkata"; pre_open_start:time=time(9); pre_open_order_entry_end:time=time(9,8); pre_open_matching_end:time=time(9,12); regular_open:time=time(9,15); regular_close:time=time(15,30); max_snapshot_age_seconds:float=300.; max_future_skew_seconds:float=5.
NSE_NIFTY_POLICY=MarketSessionPolicy(); BSE_SENSEX_POLICY=MarketSessionPolicy()

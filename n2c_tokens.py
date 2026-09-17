import sys
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot

for market in ("NIFTY", "SENSEX"):
    b = UnifiedTradingBot(market)
    print(f"[{market}]")
    print(f"  index_token    = {b.index_token!r}")
    print(f"  index_exchange = {b.index_exchange!r}")
    print(f"  index_symbol   = {b.index_symbol!r}")
    print(f"  option_exchange = {b.option_exchange!r}")
    print(f"  lot_size       = {b.lot_size}")
    print()

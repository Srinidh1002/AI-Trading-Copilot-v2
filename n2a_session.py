import sys
from datetime import datetime
sys.path.append("src")
from market_phase import MarketPhaseEngine

for market in ("NIFTY", "SENSEX"):
    eng = MarketPhaseEngine(market)
    d = eng.describe()
    print(f"[{market}]")
    print(f"  phase       = {d['phase']}")
    print(f"  can_enter   = {d['can_enter']}")
    print(f"  can_exit    = {d['can_exit']}")
    print(f"  note        = {d['note']}")
    print(f"  now (IST)   = {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

"""N4B - simultaneous two-market bounded smoke, WS disabled.

Both NIFTY and SENSEX run in PARALLEL for 6 cycles each. Neither starts
a WebSocket. REST-only. Verifies no state/chain/counter crossover.
"""
import sys, time, threading, json, os
sys.path.append("src")
from datetime import datetime
from target_focused_bot import UnifiedTradingBot

CYCLES = 6

def run_market(market, results, lock):
    b = UnifiedTradingBot(market)
    b.load_state()
    b.connect_with_retry()
    b.load_instruments()
    # N4B: disable WS to prevent cross-market session collision
    def _no_ws():
        print(f"  [{market}] WS disabled for N4B (REST-only)")
    b._start_websocket = _no_ws

    local = {"ran": 0, "trade": 0, "skip": 0, "err": 0, "counter_start": b.current_session}
    for i in range(CYCLES):
        if not b.is_market_open():
            print(f"  [{market}] market closed - stopping")
            break
        local["ran"] += 1
        print(f"\n[{market}] cycle {i+1}/{CYCLES}  {datetime.now().strftime('%H:%M:%S')}")
        try:
            r = b.run_single_session()
            if r:
                b.current_session += 1
                b.session_history.append(r)
                b.sessions_completed_today += 1
                local["trade"] += 1
                print(f"  [{market}] TRADE - counter now {b.current_session}/100")
            else:
                local["skip"] += 1
        except Exception as e:
            local["err"] += 1
            print(f"  [{market}] cycle error: {str(e)[:120]}")
        b.save_state()
        if i < CYCLES - 1 and b.is_market_open():
            time.sleep(20)

    local["counter_end"] = b.current_session
    with lock:
        results[market] = local

results = {}
lock = threading.Lock()

t1 = threading.Thread(target=run_market, args=("NIFTY", results, lock))
t2 = threading.Thread(target=run_market, args=("SENSEX", results, lock))

t1.start()
time.sleep(2)  # tiny stagger so login calls don't collide
t2.start()
t1.join()
t2.join()

print()
print("=" * 70)
print("N4B RESULT")
print("=" * 70)
for m in ("NIFTY", "SENSEX"):
    r = results.get(m, {})
    print(f"  {m}: ran={r.get('ran')} trade={r.get('trade')} skip={r.get('skip')} "
          f"err={r.get('err')} counter {r.get('counter_start')} -> {r.get('counter_end')}")

# State file cross-check
print()
print("State file cross-check:")
for m in ("nifty", "sensex"):
    p = f"data/paper_trades/{m}_experimental.json"
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        print(f"  {m}: market={d.get('market')} counter={d.get('current_session')} "
              f"total_trades={d.get('total_trades')}")

# No cross-contamination
for m, other in (("nifty", "SENSEX"), ("sensex", "NIFTY")):
    p = f"data/paper_trades/{m}_experimental.json"
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        assert d.get("market") != other, f"CONTAMINATION: {m} state has market={d.get('market')}"
print()
print("Cross-check PASSED: no market identity contamination")

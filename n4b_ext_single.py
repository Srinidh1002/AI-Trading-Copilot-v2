"""N4B extended - single market cycle runner (parameterized).

Usage: python n4b_ext_single.py <NIFTY|SENSEX> [cycles]
"""
import sys, time, json, os
sys.path.append("src")
from datetime import datetime
from target_focused_bot import UnifiedTradingBot

MARKET = (sys.argv[1].upper() if len(sys.argv) > 1 else "NIFTY")
CYCLES = int(sys.argv[2]) if len(sys.argv) > 2 else 15
CADENCE_S = 20
HARD_STOP_S = 15 * 60

b = UnifiedTradingBot(MARKET)
b.load_state()
b.connect_with_retry()
b.load_instruments()

counter_start = b.current_session
print(f"[{MARKET}] START counter={counter_start}")

cycles = 0
errors = 0
trades = 0
identity_violations = 0
start = time.time()

while cycles < CYCLES and (time.time() - start) < HARD_STOP_S:
    if not b.is_market_open():
        print(f"[{MARKET}] market closed - stopping")
        break
    cycles += 1
    print(f"\n[{MARKET}] CYCLE {cycles}/{CYCLES}  {datetime.now().strftime('%H:%M:%S')}")
    try:
        r = b.run_single_session()
        if r:
            b.current_session += 1
            b.session_history.append(r)
            b.sessions_completed_today += 1
            trades += 1
            print(f"[{MARKET}] TRADE_TALLY counter={b.current_session}")
    except Exception as e:
        errors += 1
        print(f"[{MARKET}] CYCLE_ERROR: {str(e)[:120]}")
    b.save_state()

    # Continuous isolation check
    try:
        p = f"data/paper_trades/{MARKET.lower()}_experimental.json"
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("market") != MARKET:
            identity_violations += 1
            print(f"[{MARKET}] IDENTITY_VIOLATION: state file has market={d.get('market')}")
    except Exception:
        pass

    if cycles < CYCLES and b.is_market_open():
        time.sleep(CADENCE_S)

summary = {
    "market": MARKET,
    "cycles": cycles,
    "errors": errors,
    "trades": trades,
    "counter_start": counter_start,
    "counter_end": b.current_session,
    "identity_violations": identity_violations,
    "broker_submission": b.BROKER_SUBMISSION,
    "live_execution": b.LIVE_EXECUTION,
    "execution_mode": b.EXECUTION_MODE,
    "elapsed_s": round(time.time() - start, 1),
}
print("N4B_EXT_JSON " + json.dumps(summary))

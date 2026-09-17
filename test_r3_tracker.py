"""R3 focused tests - equity first-touch tracker + persistence."""
import sys, json, tempfile, hashlib, os, shutil
sys.path.append("src")
from first_touch_tracker import (
    EquityFirstTouchTracker,
    NONE, T1_FIRST, SL_FIRST, AMBIGUOUS,
)

passed = []
def ok(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}  {detail}")
    passed.append((name, cond))

TS = "2026-09-16T09:30:00+05:30"

print("=" * 80)
print("R3 FOCUSED TESTS - first-touch tracker")
print("=" * 80)

print("\n[1] new tracker starts NONE")
t = EquityFirstTouchTracker(115.0, 130.0, 150.0, 92.0)
ok("initial result NONE", t.result() == NONE)
ok("t1_hit False", t.t1_hit is False)
ok("sl_hit False", t.sl_hit is False)

print("\n[2] bid crosses T1 first -> T1_FIRST")
t = EquityFirstTouchTracker(115.0, 130.0, 150.0, 92.0)
t.ingest_bid(116.0, TS)
ok("result T1_FIRST", t.result() == T1_FIRST)
ok("t1_hit True", t.t1_hit is True)
ok("t1_bid stored", t.t1_bid == 116.0)
ok("t1_first_seen_at set", t.t1_first_seen_at == TS)

print("\n[3] bid crosses SL first -> SL_FIRST")
t = EquityFirstTouchTracker(115.0, 130.0, 150.0, 92.0)
t.ingest_bid(91.0, TS)
ok("result SL_FIRST", t.result() == SL_FIRST)
ok("sl_hit True", t.sl_hit is True)
ok("sl_bid stored", t.sl_bid == 91.0)

print("\n[4] after T1_FIRST, later SL crossing does not flip")
t = EquityFirstTouchTracker(115.0, 130.0, 150.0, 92.0)
t.ingest_bid(116.0, "2026-09-16T09:30:00+05:30")
t.ingest_bid(91.0,  "2026-09-16T09:35:00+05:30")
ok("result stays T1_FIRST", t.result() == T1_FIRST)
ok("sl_hit recorded", t.sl_hit is True)

print("\n[5] after SL_FIRST, later T1 crossing does not flip")
t = EquityFirstTouchTracker(115.0, 130.0, 150.0, 92.0)
t.ingest_bid(91.0,  "2026-09-16T09:30:00+05:30")
t.ingest_bid(116.0, "2026-09-16T09:35:00+05:30")
ok("result stays SL_FIRST", t.result() == SL_FIRST)
ok("t1_hit recorded", t.t1_hit is True)

print("\n[6] timestamps stored once")
t = EquityFirstTouchTracker(115.0, 130.0, 150.0, 92.0)
t.ingest_bid(116.0, "2026-09-16T09:30:00+05:30")
first_t1_at = t.t1_first_seen_at
t.ingest_bid(120.0, "2026-09-16T09:31:00+05:30")
ok("t1_first_seen_at unchanged",
   t.t1_first_seen_at == first_t1_at)

print("\n[7] crossing bids stored correctly")
t = EquityFirstTouchTracker(115.0, 130.0, 150.0, 92.0)
t.ingest_bid(116.0, TS)
t.ingest_bid(119.0, "2026-09-16T09:31:00+05:30")
ok("t1_bid is the crossing bid (116), not later (119)",
   t.t1_bid == 116.0)

print("\n[8] last_valid_bid updated every accepted ingest")
t = EquityFirstTouchTracker(115.0, 130.0, 150.0, 92.0)
t.ingest_bid(100.0, "2026-09-16T09:30:00+05:30")
t.ingest_bid(105.0, "2026-09-16T09:31:00+05:30")
ok("last_valid_bid updated", t.last_valid_bid == 105.0)
ok("sequence incremented", t.first_touch_sequence == 2)

print("\n[9] save / reload preserves tracker exactly")
t = EquityFirstTouchTracker(115.0, 130.0, 150.0, 92.0)
t.ingest_bid(116.0, "2026-09-16T09:30:00+05:30")
t.ingest_bid(117.0, "2026-09-16T09:31:00+05:30")
saved = t.to_state()
t2 = EquityFirstTouchTracker.from_state(saved)
ok("result preserved", t2.result() == t.result())
ok("t1_bid preserved", t2.t1_bid == t.t1_bid)
ok("t1_first_seen_at preserved", t2.t1_first_seen_at == t.t1_first_seen_at)
ok("sequence preserved", t2.first_touch_sequence == t.first_touch_sequence)
ok("last_valid_bid preserved", t2.last_valid_bid == t.last_valid_bid)

print("\n[10] AMBIGUOUS when T1 and SL crossed in same observation")
t = EquityFirstTouchTracker(t1_price=100.0, sl_price=100.0)
t.ingest_bid(100.0, TS)
ok("result AMBIGUOUS", t.result() == AMBIGUOUS)

print("\n[11] legacy state without tracker fields loads safely")
legacy = {"t1_price": 115.0, "sl_price": 92.0}
t = EquityFirstTouchTracker.from_state(legacy)
ok("loads with NONE result", t.result() == NONE)
ok("t1_hit defaults False", t.t1_hit is False)
ok("sequence defaults 0", t.first_touch_sequence == 0)

print("\n[12] active V2 genesis + archived Day-1 unchanged")
def sha256(p):
    if not os.path.exists(p): return None
    with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()
_ARCH = "data/paper_trades/_archived_NS_precert_20260915"
for label, active_fname, arch_fname, v1_prefix, day1_prefix in [
    ("nifty_experimental",
     "data/paper_trades/nifty_experimental.json",
     _ARCH + "/nifty_experimental.json",
     "bbaace49", "106e57f3"),
    ("sensex_experimental",
     "data/paper_trades/sensex_experimental.json",
     _ARCH + "/sensex_experimental.json",
     "707dffbe", "a1239db0"),
]:
    h_act = sha256(active_fname)
    h_arc = sha256(arch_fname)
    ok(f"{label} unchanged",
       (h_act and h_act.startswith(v1_prefix)) and (h_arc and h_arc.startswith(day1_prefix)),
       f"active={h_act[:8] if h_act else 'MISS'} archive={h_arc[:8] if h_arc else 'MISS'}")

n_pass = sum(1 for _, c in passed if c)
n_fail = sum(1 for _, c in passed if not c)
print()
print(f"R3 FOCUSED TESTS: {n_pass}/{len(passed)} passed")
if n_fail:
    for n, c in passed:
        if not c: print(f"  FAIL: {n}")
    sys.exit(1)
print("R3 FOCUSED TESTS: ALL PASSED")

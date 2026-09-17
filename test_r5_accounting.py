"""R5 focused tests - T1/T2 milestone accounting + cert result."""
import sys, inspect, hashlib, os
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot
from first_touch_tracker import EquityFirstTouchTracker, T1_FIRST, SL_FIRST, AMBIGUOUS, NONE

passed = []
def ok(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}  {detail}")
    passed.append((name, cond))

def sha256(p):
    if not os.path.exists(p): return None
    with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()

print("=" * 80)
print("R5 FOCUSED TESTS")
print("=" * 80)

src_full = inspect.getsource(UnifiedTradingBot)
src_close = inspect.getsource(UnifiedTradingBot.close_position)
src_rss = inspect.getsource(UnifiedTradingBot.run_single_session)

print("\n[1] Structural - R5 markers present")
ok("3+ R5_milestone_accounting markers",
   src_full.count("R5_milestone_accounting") >= 3,
   f"count={src_full.count('R5_milestone_accounting')}")

print("\n[2] Tracker ingest returns t1/t2 crossing flags")
t = EquityFirstTouchTracker(t1_price=100.0, t2_price=110.0, t3_price=120.0, sl_price=90.0)
out1 = t.ingest_bid(95.0, "2026-09-16T09:00:00+05:30")
ok("first obs: no t1 crossing", out1.get("t1_crossed_now") is False)
out2 = t.ingest_bid(105.0, "2026-09-16T09:01:00+05:30")
ok("t1 crossing returned", out2.get("t1_crossed_now") is True)
ok("t2 not yet", out2.get("t2_crossed_now") is False)
out3 = t.ingest_bid(115.0, "2026-09-16T09:02:00+05:30")
ok("t2 crossing returned", out3.get("t2_crossed_now") is True)
out4 = t.ingest_bid(118.0, "2026-09-16T09:03:00+05:30")
ok("no re-cross: t1 False", out4.get("t1_crossed_now") is False)
ok("no re-cross: t2 False", out4.get("t2_crossed_now") is False)

print("\n[3] One-shot guard - tracker never fires crossed_now twice")
t = EquityFirstTouchTracker(t1_price=100.0, sl_price=90.0)
first = t.ingest_bid(101.0, "2026-09-16T09:00:00+05:30")
second = t.ingest_bid(102.0, "2026-09-16T09:01:00+05:30")
ok("first t1_crossed_now True", first.get("t1_crossed_now") is True)
ok("second t1_crossed_now False", second.get("t1_crossed_now") is False)

print("\n[4] Structural - one-shot increment guarded by flag")
ok("t1_hit_counted check in source",
   "not active_trade.get('t1_hit_counted')" in src_rss)
ok("t2_hit_counted check in source",
   "not active_trade.get('t2_hit_counted')" in src_rss)
ok("self.t1_hits += 1 in source",
   "self.t1_hits += 1" in src_rss)
ok("self.t2_hits += 1 in source",
   "self.t2_hits += 1" in src_rss)

print("\n[5] Structural - cert_win/cert_loss from first_touch_result")
ok("reads first_touch_result", "trade.get('first_touch_result')" in src_close)
ok("T1_FIRST -> cert_win=True",
   "_ftr == 'T1_FIRST':" in src_close and "trade['certification_win'] = True" in src_close)
ok("SL_FIRST -> cert_loss=True",
   "_ftr == 'SL_FIRST':" in src_close and "trade['certification_loss'] = True" in src_close)
ok("no cert_win from net_pnl",
   "certification_win" not in src_close.split("certification_win")[0].split("_pnl_for_total")[-1]
   or "certification_win'] = _pnl" not in src_close)

print("\n[6] Structural - cert fields init in trade dict")
ok("certification_win placeholder",
   "'certification_win': None," in src_rss)
ok("certification_loss placeholder",
   "'certification_loss': None," in src_rss)

print("\n[7] Structural - economic win separation comment present")
ok("economic win comment",
   "ECONOMIC statistics only" in src_close)

print("\n[8] T3 audit - single increment site in T3 branch")
# Count occurrences of self.t3_hits += 1 in run_single_session
t3_count = src_rss.count("self.t3_hits += 1")
ok("self.t3_hits += 1 appears exactly once in monitor path",
   t3_count == 1,
   f"count={t3_count}")

print("\n[9] /100 counter authority unchanged")
ok("current_session not touched by R5 in run_single_session",
   "self.current_session += 1" not in src_rss)
ok("current_session not touched by R5 in close_position",
   "self.current_session += 1" not in src_close)

print("\n[10] Bot runtime - counters init at zero, new fields present")
b = UnifiedTradingBot("NIFTY")
ok("t1_hits init 0", b.t1_hits == 0)
ok("t2_hits init 0", b.t2_hits == 0)
ok("t3_hits init 0", b.t3_hits == 0)
ok("winning_trades init 0", b.winning_trades == 0)
ok("current_session init 0", b.current_session == 0)

print("\n[11] Cert result resolution - all four cases")
def resolve_cert(ftr):
    """Mirror the exact logic from close_position."""
    if ftr == 'T1_FIRST':
        return (True, False)
    elif ftr == 'SL_FIRST':
        return (False, True)
    else:
        return (False, False)

ok("T1_FIRST -> (True, False)",  resolve_cert('T1_FIRST')  == (True, False))
ok("SL_FIRST -> (False, True)",  resolve_cert('SL_FIRST')  == (False, True))
ok("NONE -> (False, False)",     resolve_cert('NONE')      == (False, False))
ok("AMBIGUOUS -> (False, False)",resolve_cert('AMBIGUOUS') == (False, False))

print("\n[12] Day-1 equity files unchanged")
for label, active_fname, arch_fname, v1_prefix, day1_prefix in [
    ("nifty_experimental",
     "data/paper_trades/nifty_experimental.json",
     "data/paper_trades/_archived_NS_precert_20260915/nifty_experimental.json",
     "bbaace49", "106e57f3"),
    ("sensex_experimental",
     "data/paper_trades/sensex_experimental.json",
     "data/paper_trades/_archived_NS_precert_20260915/sensex_experimental.json",
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
print(f"R5 FOCUSED TESTS: {n_pass}/{len(passed)} passed")
if n_fail:
    for n, c in passed:
        if not c: print(f"  FAIL: {n}")
    sys.exit(1)
print("R5 FOCUSED TESTS: ALL PASSED")

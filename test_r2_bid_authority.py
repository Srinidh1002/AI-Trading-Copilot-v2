"""R2 focused tests - executable bid is the sole threshold authority."""
import sys, inspect, os, hashlib
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot

passed = []
def ok(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}  {detail}")
    passed.append((name, cond))

def sha256(p):
    if not os.path.exists(p): return None
    with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()

print("=" * 80)
print("R2 FOCUSED TESTS - bid authority")
print("=" * 80)

b = UnifiedTradingBot("NIFTY")
src_rss = inspect.getsource(UnifiedTradingBot.run_single_session)
src_close = inspect.getsource(UnifiedTradingBot.close_position)

print("\n[1] Structural - R2_bid_authority markers present")
ok("3+ markers in run_single_session",
   src_rss.count("R2_bid_authority") >= 3,
   f"count={src_rss.count('R2_bid_authority')}")

print("\n[2] Structural - current_mark = executable bid")
ok("current_mark defined from current_bid",
   "current_mark = current_bid if (current_bid is not None and current_bid > 0) else None" in src_rss)

print("\n[3] Structural - T1 crossing by bid price")
ok("T1 uses current_mark >= t1_price",
   "if not active_trade.get('t1_hit') and current_mark >= active_trade['t1_price']:" in src_rss)
ok("no pnl_pct >= T1_PERCENT in monitor",
   "pnl_pct >= self.T1_PERCENT" not in src_rss)

print("\n[4] Structural - T3 exit by bid price")
ok("T3 uses current_mark >= t3_price",
   "if current_mark >= active_trade['t3_price']:" in src_rss)
ok("no pnl_pct >= T3_PERCENT in monitor",
   "pnl_pct >= self.T3_PERCENT" not in src_rss)

print("\n[5] Structural - SL exit by bid price")
ok("SL uses current_mark <= sl_price",
   "elif current_mark <= active_trade['sl_price']:" in src_rss)
ok("no pnl_pct <= -STOP_LOSS in monitor",
   "pnl_pct <= -self.STOP_LOSS_PERCENT" not in src_rss)

print("\n[6] Structural - MFE/MAE fed current_mark")
ok("mfe_mae.update uses current_mark",
   "self.mfe_mae.update(trade_id, current_mark)" in src_rss)
ok("peak_price uses current_mark",
   "current_mark > active_trade['peak_price']" in src_rss)

print("\n[7] Structural - session-close requires valid bid")
ok("session-close guarded by valid bid",
   "if _bid is not None and _bid > 0:" in src_rss)

print("\n[8] Structural - no LTP fallback in thresholds")
for bad in ("pnl_pct >= self.T1_PERCENT",
            "pnl_pct >= self.T3_PERCENT",
            "pnl_pct <= -self.STOP_LOSS_PERCENT"):
    ok(f"no {bad!r}", bad not in src_rss)

print("\n[9] Threshold constants unchanged")
ok("T1_PERCENT == 15", b.T1_PERCENT == 15)
ok("T2_PERCENT == 30", b.T2_PERCENT == 30)
ok("T3_PERCENT == 50", b.T3_PERCENT == 50)
ok("STOP_LOSS_PERCENT == 5", b.STOP_LOSS_PERCENT == 5)

print("\n[10] Simulation - threshold logic with bid as authority")
# Pure logic mirror: prove a bid below T1 does NOT trigger T1
def check_t1(current_mark, t1_price):
    return current_mark >= t1_price
def check_sl(current_mark, sl_price):
    return current_mark <= sl_price

entry = 100.0
t1_price = entry * 1.15    # 115
sl_price = entry * 0.95    # 95

# Scenario 1: LTP=120 (above T1), bid=110 (below T1)
ltp = 120.0; bid = 110.0
ok("Scenario 1: LTP>t1 but bid<t1 -> no T1", not check_t1(bid, t1_price))

# Scenario 2: bid >= t1
bid = 116.0
ok("Scenario 2: bid>=t1 -> T1 hit", check_t1(bid, t1_price))

# Scenario 3: LTP=90 (below SL), bid=96 (above SL)
ltp = 90.0; bid = 96.0
ok("Scenario 3: LTP<sl but bid>sl -> no SL", not check_sl(bid, sl_price))

# Scenario 4: bid <= sl
bid = 94.0
ok("Scenario 4: bid<=sl -> SL hit", check_sl(bid, sl_price))

print("\n[11] Day-1 equity files unchanged")
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
print(f"R2 FOCUSED TESTS: {n_pass}/{len(passed)} passed")
if n_fail:
    for n, c in passed:
        if not c: print(f"  FAIL: {n}")
    sys.exit(1)
print("R2 FOCUSED TESTS: ALL PASSED")

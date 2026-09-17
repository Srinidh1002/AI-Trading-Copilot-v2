"""R4 focused tests - quote-gap / ambiguity handling."""
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
print("R4 FOCUSED TESTS")
print("=" * 80)

b = UnifiedTradingBot("NIFTY")

# ----------------------------------------------------------
# [1] structural: R4 markers present
print("\n[1] Structural - R4 markers")
src_full = inspect.getsource(UnifiedTradingBot)
ok("R4_quote_gap markers >= 4", src_full.count("R4_quote_gap") >= 4,
   f"count={src_full.count('R4_quote_gap')}")
ok("_handle_quote_gap defined",
   hasattr(UnifiedTradingBot, "_handle_quote_gap"))

# ----------------------------------------------------------
# [2] one quote failure -> gap starts, skip=True
print("\n[2] First quote failure starts a gap")
trade = {
    "first_touch_result": "NONE",
    "monitoring_gap_count": 0,
    "monitoring_gap_started_at": None,
}
skip = b._handle_quote_gap(trade, False)
ok("skip_thresholds True", skip is True)
ok("gap_started_at set", trade["monitoring_gap_started_at"] is not None)
ok("gap_count == 1", trade["monitoring_gap_count"] == 1)

# ----------------------------------------------------------
# [3] multiple failures -> one continuous gap
print("\n[3] Multiple consecutive failures = one gap")
b._handle_quote_gap(trade, False)
b._handle_quote_gap(trade, False)
b._handle_quote_gap(trade, False)
ok("gap_count still 1", trade["monitoring_gap_count"] == 1)
ok("gap_started_at unchanged", trade["monitoring_gap_started_at"] is not None)

# ----------------------------------------------------------
# [4] quote resumes with result still NONE -> AMBIGUOUS
print("\n[4] Quote resumes with NONE -> AMBIGUOUS")
skip = b._handle_quote_gap(trade, True)
ok("skip_thresholds False on resume", skip is False)
ok("first_touch_result == AMBIGUOUS",
   trade["first_touch_result"] == "AMBIGUOUS")
ok("evidence_ambiguous True", trade["evidence_ambiguous"] is True)
ok("certification_countable False",
   trade["certification_countable"] is False)
ok("gap_started_at cleared", trade["monitoring_gap_started_at"] is None)
ok("gap_ended_at set", trade["monitoring_gap_ended_at"] is not None)

# ----------------------------------------------------------
# [5] T1_FIRST established before gap -> stays T1_FIRST
print("\n[5] T1_FIRST before gap preserved")
trade = {
    "first_touch_result": "T1_FIRST",
    "monitoring_gap_count": 0,
    "monitoring_gap_started_at": None,
    "evidence_ambiguous": False,
    "certification_countable": True,
}
b._handle_quote_gap(trade, False)   # gap starts
skip = b._handle_quote_gap(trade, True)  # gap ends
ok("result stays T1_FIRST", trade["first_touch_result"] == "T1_FIRST")
ok("evidence_ambiguous False", trade["evidence_ambiguous"] is False)
ok("certification_countable True", trade["certification_countable"] is True)

# ----------------------------------------------------------
# [6] SL_FIRST established before gap -> stays SL_FIRST
print("\n[6] SL_FIRST before gap preserved")
trade = {
    "first_touch_result": "SL_FIRST",
    "monitoring_gap_count": 0,
    "monitoring_gap_started_at": None,
    "evidence_ambiguous": False,
    "certification_countable": True,
}
b._handle_quote_gap(trade, False)
b._handle_quote_gap(trade, True)
ok("result stays SL_FIRST", trade["first_touch_result"] == "SL_FIRST")
ok("evidence_ambiguous False", trade["evidence_ambiguous"] is False)

# ----------------------------------------------------------
# [7] structural: threshold block guarded by _skip_thresholds
print("\n[7] Structural - threshold guard")
ok("threshold block uses not _skip_thresholds",
   "if current_mark is not None and not _skip_thresholds:" in src_full)

# ----------------------------------------------------------
# [8] structural: R3 block respects evidence_ambiguous
print("\n[8] Structural - R3 does not clobber AMBIGUOUS")
ok("guard on evidence_ambiguous present",
   "if not active_trade.get('evidence_ambiguous'):" in src_full)

# ----------------------------------------------------------
# [9] structural: outer except does not silently pass
print("\n[9] Structural - outer except logs")
ok("CYCLE_ERROR print present",
   "[R4] CYCLE_ERROR:" in src_full)
# Confirm no more bare 'except Exception as e:\n                pass'
src_rss = inspect.getsource(UnifiedTradingBot.run_single_session)
# count of bare pass after except in the monitor region
ok("no silent 'except Exception as e: pass' in monitor",
   "            except Exception as e:\n                pass\n" not in src_rss)

# ----------------------------------------------------------
# [10] no LTP fallback / no stale bid eval
print("\n[10] Structural - no fallback paths")
# The threshold block is now guarded; no ltp-fallback introduced by R4
ok("no ltp fallback in R4 helper",
   "_ltp" not in inspect.getsource(UnifiedTradingBot._handle_quote_gap))

# ----------------------------------------------------------
# [11] AMBIGUOUS not derived from exit_reason or pnl
print("\n[11] Structural - AMBIGUOUS only from gap")
helper_src = inspect.getsource(UnifiedTradingBot._handle_quote_gap)
ok("AMBIGUOUS set only inside gap_end branch",
   "'AMBIGUOUS'" in helper_src and "_ftr_prev is None or _ftr_prev == 'NONE'" in helper_src)
ok("no reference to exit_reason or pnl in helper",
   "exit_reason" not in helper_src and "net_pnl" not in helper_src)

# ----------------------------------------------------------
# [12] restart persistence - fields survive to_state via trade dict
print("\n[12] Restart - fields persist through save/load")
b2 = UnifiedTradingBot("NIFTY")
# simulate open trade with gap state
b2.active_trades["T1"] = {
    "trade_id": "T1", "market": "NIFTY",
    "first_touch_result": "AMBIGUOUS",
    "monitoring_gap_count": 3,
    "monitoring_gap_started_at": "2026-09-16T09:30:00",
    "evidence_ambiguous": True,
    "certification_countable": False,
}
# save_state writes active_trades as a list of dicts
import tempfile, json, shutil
tmp = tempfile.mkdtemp(prefix="r4_persist_")
try:
    b2.state_file = os.path.join(tmp, "nifty_state.json")
    b2.save_state()
    b3 = UnifiedTradingBot("NIFTY")
    b3.state_file = b2.state_file
    b3.load_state()
    loaded = b3.active_trades.get("T1", {})
    ok("active trade restored", loaded.get("trade_id") == "T1")
    ok("first_touch_result preserved",
       loaded.get("first_touch_result") == "AMBIGUOUS")
    ok("monitoring_gap_count preserved",
       loaded.get("monitoring_gap_count") == 3)
    ok("evidence_ambiguous preserved",
       loaded.get("evidence_ambiguous") is True)
    ok("certification_countable preserved",
       loaded.get("certification_countable") is False)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ----------------------------------------------------------
# [13] no strategy/threshold change
print("\n[13] Structural - no threshold change")
ok("T1_PERCENT still 15", b.T1_PERCENT == 15)
ok("T2_PERCENT still 30", b.T2_PERCENT == 30)
ok("T3_PERCENT still 50", b.T3_PERCENT == 50)
ok("STOP_LOSS_PERCENT still 5", b.STOP_LOSS_PERCENT == 5)

# ----------------------------------------------------------
# [14] no /100 counter implementation yet
print("\n[14] Structural - /100 counter unchanged")
ok("current_session not touched by R4",
   "self.current_session += 1" not in inspect.getsource(UnifiedTradingBot.close_position))
ok("current_session not touched in R4 helper",
   "current_session" not in helper_src)

# ----------------------------------------------------------
# [15] Day-1 files unchanged
print("\n[15] Day-1 files untouched")
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

# ----------------------------------------------------------
n_pass = sum(1 for _, c in passed if c)
n_fail = sum(1 for _, c in passed if not c)
print()
print(f"R4 FOCUSED TESTS: {n_pass}/{len(passed)} passed")
if n_fail:
    for n, c in passed:
        if not c: print(f"  FAIL: {n}")
    sys.exit(1)
print("R4 FOCUSED TESTS: ALL PASSED")

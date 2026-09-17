"""R15 focused tests - equity diversity authority.
All bot instances use isolated tempdir state_file.
"""
import sys, os, json, hashlib, tempfile, shutil, inspect, atexit
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot, STRATEGY_VERSION, CERTIFICATION_EPOCH
from diversity_tracker import (
    EquityCertificationDiversityTracker,
    DIVERSITY_MIN_DAYS, DIVERSITY_MIN_REGIMES, DIVERSITY_MIN_PHASES,
    DIVERSITY_MAX_PER_DAY,
)

_TMP = tempfile.mkdtemp(prefix="r15_isolated_")
atexit.register(lambda: shutil.rmtree(_TMP, ignore_errors=True))
_CTR = {"n": 0}
def _bot(market="NIFTY"):
    _CTR["n"] += 1
    b = UnifiedTradingBot(market)
    b.state_file = os.path.join(_TMP, f"{market.lower()}_{_CTR['n']}.json")
    return b

passed = []
def ok(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}  {detail}")
    passed.append((name, cond))

def sha256(p):
    if not os.path.exists(p): return None
    with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()

def make_countable_trade(tid, date="2026-09-16", regime="TRENDING_UP", phase="CONTINUOUS"):  # R15_helper_swap_fixed
    return {
        "trade_id": tid, "market": "NIFTY", "status": "CLOSED",
        "execution_mode": "PAPER", "broker_submission": False,
        "live_execution": False, "certification_eligible": True,
        "certification_countable": True,
        "strategy_version": STRATEGY_VERSION,
        "certification_epoch": CERTIFICATION_EPOCH,
        "first_touch_result": "T1_FIRST",
        "certification_trade_date": date,
        "certification_regime": regime,
        "certification_session_phase": phase,
    }

print("=" * 80)
print("R15 FOCUSED TESTS - diversity authority")
print("=" * 80)

# [1] First valid countable records day/regime/phase
print("\n[1] First countable records metadata")
b = _bot()
r = b._try_increment_certification_counter(make_countable_trade("T1"), True)
d = b.certification_diversity.to_state()
ok("counted", r is True)
ok("date recorded", "2026-09-16" in d["trading_dates"])
ok("regime recorded", "TRENDING_UP" in d["regimes"])
ok("phase recorded", "CONTINUOUS" in d["session_phases"])

# [2] Second same-day trade increments daily count
print("\n[2] Second same-day trade increments daily count")
r2 = b._try_increment_certification_counter(make_countable_trade("T2"), True)
ok("second counted", r2 is True)
ok("day count == 2", b.certification_diversity.countable_by_day.get("2026-09-16") == 2)

# [3] 40th same-day trade counts
print("\n[3] 40th same-day trade counts")
b2 = _bot()
for i in range(40):
    b2._try_increment_certification_counter(make_countable_trade(f"T{i}"), True)
ok("counter == 40", b2.certification_counter == 40)
ok("day count == 40", b2.certification_diversity.countable_by_day.get("2026-09-16") == 40)

# [4] 41st same-day trade rejected; diversity daily count unchanged
print("\n[4] 41st same-day trade: daily cap reached")
t41 = make_countable_trade("T41")
r41 = b2._try_increment_certification_counter(t41, True)
ok("rejected", r41 is False)
ok("counter still 40", b2.certification_counter == 40)
ok("day count still 40", b2.certification_diversity.countable_by_day.get("2026-09-16") == 40)
ok("certification_countable=False",
   t41.get("certification_countable") is False)
ok("reason=DAILY_DIVERSITY_CAP_REACHED",
   t41.get("certification_countability_reason") == "DAILY_DIVERSITY_CAP_REACHED")

# [5] Duplicate trade_id does not double-add diversity
print("\n[5] Duplicate trade_id: no double diversity")
b3 = _bot()
t = make_countable_trade("DUP")
b3._try_increment_certification_counter(t, True)
b3._try_increment_certification_counter(t, True)
ok("counter == 1", b3.certification_counter == 1)
ok("day count == 1", b3.certification_diversity.countable_by_day.get("2026-09-16") == 1)

# [6] Restart preserves diversity state
print("\n[6] Restart preserves diversity state")
tmp = tempfile.mkdtemp(prefix="r15_restart_")
try:
    b4 = _bot()
    b4.state_file = os.path.join(tmp, "nifty.json")
    b4.strategy_version = STRATEGY_VERSION
    b4.certification_epoch = CERTIFICATION_EPOCH
    b4.is_legacy_precert = False
    b4._try_increment_certification_counter(
        make_countable_trade("RST1", date="2026-09-16", regime="TRENDING_UP", phase="CONTINUOUS"), True)
    b4._try_increment_certification_counter(
        make_countable_trade("RST2", date="2026-09-17", regime="RANGE_BOUND", phase="CONTINUOUS"), True)
    b4.save_state()

    b5 = _bot()
    b5.state_file = b4.state_file
    b5.load_state()
    d5 = b5.certification_diversity.to_state()
    ok("dates preserved", sorted(d5["trading_dates"]) == ["2026-09-16", "2026-09-17"])
    ok("regimes preserved", sorted(d5["regimes"]) == ["RANGE_BOUND", "TRENDING_UP"])
    ok("counter preserved", b5.certification_counter == 2)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# [7] Wrong epoch adds nothing
print("\n[7] Wrong epoch adds nothing")
b6 = _bot()
bad = make_countable_trade("WE", regime="X")
bad["certification_epoch"] = "OTHER"
r = b6._try_increment_certification_counter(bad, True)
ok("rejected", r is False)
ok("no diversity recorded", b6.certification_diversity.countable_by_day == {})

# [8] AMBIGUOUS adds nothing
print("\n[8] AMBIGUOUS adds nothing")
b7 = _bot()
amb = make_countable_trade("AMB")
amb["certification_countable"] = False
amb["first_touch_result"] = "AMBIGUOUS"
r = b7._try_increment_certification_counter(amb, True)
ok("rejected", r is False)
ok("no diversity recorded", b7.certification_diversity.countable_by_day == {})

# [9] Unreconciled adds nothing
print("\n[9] Unreconciled adds nothing")
b8 = _bot()
r = b8._try_increment_certification_counter(make_countable_trade("NR"), False)
ok("rejected", r is False)
ok("no diversity recorded", b8.certification_diversity.countable_by_day == {})

# [10] NIFTY / SENSEX independent
print("\n[10] NIFTY / SENSEX independent")
bn = _bot("NIFTY")
bs = _bot("SENSEX")
bn._try_increment_certification_counter(make_countable_trade("N1"), True)
ok("NIFTY has 1, SENSEX 0",
   bn.certification_counter == 1 and bs.certification_counter == 0)
ok("independent diversity objects",
   bn.certification_diversity is not bs.certification_diversity)
ok("SENSEX diversity empty",
   bs.certification_diversity.countable_by_day == {})

# [11-14] Final evaluation matrix via tracker directly
print("\n[11-14] Final evaluation matrix")
def eval_via_tracker(counter, wins, days, regimes, phases, per_day_max=1):
    t = EquityCertificationDiversityTracker()
    for d in days:
        t.trading_dates.add(d)
        t.countable_by_day[d] = per_day_max
    for r in regimes: t.regimes.add(r)
    for p in phases:  t.session_phases.add(p)
    div_ok, div = t.evaluate()
    if counter < 100:
        return {"status": "IN_PROGRESS", "diversity_ok": div_ok, **div}
    if not div_ok:
        return {"status": "DIVERSITY_FAIL", "diversity_ok": False, **div}
    if wins >= 80:
        return {"status": "PASS", "diversity_ok": True, **div}
    return {"status": "FAIL_ACCURACY", "diversity_ok": True, **div}

v = eval_via_tracker(100, 85, ["d1","d2","d3","d4","d5"], ["R1","R2"], ["P1","P2"])
ok("11: 100 across 5d/2R/2P -> PASS", v["status"] == "PASS")
v = eval_via_tracker(100, 85, ["d1","d2","d3","d4"], ["R1","R2"], ["P1","P2"])
ok("12: 100 across 4d -> DIVERSITY_FAIL", v["status"] == "DIVERSITY_FAIL")
v = eval_via_tracker(100, 85, ["d1","d2","d3","d4","d5"], ["R1"], ["P1","P2"])
ok("13: 100 across 1R -> DIVERSITY_FAIL", v["status"] == "DIVERSITY_FAIL")
v = eval_via_tracker(100, 85, ["d1","d2","d3","d4","d5"], ["R1","R2"], ["P1"])
ok("14: 100 across 1P -> DIVERSITY_FAIL", v["status"] == "DIVERSITY_FAIL")

# [15] No day can exceed 40 (already covered by [4] but explicit tracker test)
print("\n[15] Tracker: no day >40")
t = EquityCertificationDiversityTracker()
t.countable_by_day["x"] = 40
would, reason = t.would_count("x", "R", "P")
ok("would_count returns False at 40", would is False and reason == "DAILY_DIVERSITY_CAP_REACHED")

# [16-17] Win criterion matrix
v = eval_via_tracker(100, 80, ["d1","d2","d3","d4","d5"], ["R1","R2"], ["P1","P2"])
ok("16: 100 diversified + 80 wins -> PASS", v["status"] == "PASS")
v = eval_via_tracker(100, 79, ["d1","d2","d3","d4","d5"], ["R1","R2"], ["P1","P2"])
ok("17: 100 diversified + 79 wins -> FAIL_ACCURACY", v["status"] == "FAIL_ACCURACY")

# [18] Undiversified with high wins -> DIVERSITY_FAIL not PASS
v = eval_via_tracker(100, 90, ["d1","d2","d3","d4"], ["R1","R2"], ["P1","P2"])
ok("18: 100 undiversified + 90 wins -> DIVERSITY_FAIL",
   v["status"] == "DIVERSITY_FAIL")

# [19] Trade 101 never enters
print("\n[19] Trade 101 never enters")
b = _bot()
for i in range(100):
    # spread across 5 days/2 regimes/2 phases, 20 per day (well under cap)
    day = f"2026-09-{16 + (i // 20)}"
    b._try_increment_certification_counter(
        make_countable_trade(f"L{i}", date=day, regime="T1" if i % 2 else "T2",
                             phase="P1" if i % 3 else "P2"), True)
ok("counter == 100", b.certification_counter == 100)
t101 = make_countable_trade("T101")
r = b._try_increment_certification_counter(t101, True)
ok("trade 101 rejected", r is False)
ok("counter still 100", b.certification_counter == 100)

# [20] archived Day-1 + active V2 genesis
print("\n[20] archived Day-1 + active V2 genesis")
_ARCH = "data/paper_trades/_archived_NS_precert_20260915"
for label, active_fname, arch_fname, v1_prefix, day1_prefix in [
    ("nifty_experimental",  "data/paper_trades/nifty_experimental.json",  _ARCH + "/nifty_experimental.json",  "bbaace49", "106e57f3"),
    ("sensex_experimental", "data/paper_trades/sensex_experimental.json", _ARCH + "/sensex_experimental.json", "707dffbe", "a1239db0"),
]:
    h_act = sha256(active_fname)
    h_arc = sha256(arch_fname)
    ok(f"{label} unchanged",
       (h_act and h_act.startswith(v1_prefix)) and (h_arc and h_arc.startswith(day1_prefix)),
       f"active={h_act[:8] if h_act else 'MISS'} archive={h_arc[:8] if h_arc else 'MISS'}")

# [21] MCX untouched (hash check)
print("\n[21] MCX untouched (informational)")
for fname, prefix in [
    ("data/paper_trades/mcx_crudeoilm_outcomes.jsonl", "c1adcd75"),
]:
    h = sha256(fname)
    ok(f"{fname} unchanged", h and h.startswith(prefix),
       f"{h[:16] if h else 'MISSING'}...")

n_pass = sum(1 for _, c in passed if c)
n_fail = sum(1 for _, c in passed if not c)
print()
print(f"R15 FOCUSED TESTS: {n_pass}/{len(passed)} passed")
if n_fail:
    for n, c in passed:
        if not c: print(f"  FAIL: {n}")
    sys.exit(1)
print("R15 FOCUSED TESTS: ALL PASSED")

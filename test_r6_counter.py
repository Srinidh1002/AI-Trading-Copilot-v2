"""R6 focused tests - /100 certification counter authority."""
import sys, inspect, tempfile, shutil, os, hashlib, json
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot, STRATEGY_VERSION, CERTIFICATION_EPOCH

import tempfile as _tf

# fix_r6_test_isolated - every test bot writes to a private tempdir
_TMP = _tf.mkdtemp(prefix="r6_isolated_")
_CTR = {"n": 0}

def _bot(market="NIFTY"):
    from target_focused_bot import UnifiedTradingBot as _U
    _CTR["n"] += 1
    b = _U(market)
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

print("=" * 80)
print("R6 FOCUSED TESTS - cert counter")
print("=" * 80)

b = _bot("NIFTY")

# helper: synthetic countable trade
from certification_phase import CERT_PHASE_EARLY


def make_trade(**overrides):
    t = {
        "trade_id": "TRD_TEST_001",
        "market": "NIFTY",
        "status": "CLOSED",
        "execution_mode": "PAPER",
        "broker_submission": False,
        "live_execution": False,
        "certification_eligible": True,
        "certification_countable": True,
        "strategy_version": STRATEGY_VERSION,
        "certification_epoch": CERTIFICATION_EPOCH,
        "first_touch_result": "T1_FIRST",
        "certification_trade_date": "2026-09-16",
        "certification_regime": "TRENDING_UP",
        "certification_session_phase": CERT_PHASE_EARLY,
    }
    t.update(overrides)
    return t

print("\n[1] Fresh bot has zero cert counters")
ok("cert counter 0", b.certification_counter == 0)
ok("cert wins 0", b.certification_wins == 0)
ok("cert losses 0", b.certification_losses == 0)
ok("counted_trade_ids empty set", b.counted_trade_ids == set())

print("\n[2] T1_FIRST countable -> +1 counter +1 win")
t = make_trade()
r = b._try_increment_certification_counter(t, True)
ok("increment returned True", r is True)
ok("counter 1", b.certification_counter == 1)
ok("wins 1", b.certification_wins == 1)
ok("losses 0", b.certification_losses == 0)
ok("trade_id recorded", "TRD_TEST_001" in b.counted_trade_ids)

print("\n[3] SL_FIRST countable -> +1 counter +1 loss")
b2 = _bot("NIFTY")
t = make_trade(trade_id="TRD_TEST_002", first_touch_result="SL_FIRST")
r = b2._try_increment_certification_counter(t, True)
ok("increment returned True", r is True)
ok("counter 1", b2.certification_counter == 1)
ok("wins 0", b2.certification_wins == 0)
ok("losses 1", b2.certification_losses == 1)

print("\n[4] Duplicate trade_id does not double-count")
b3 = _bot("NIFTY")
t = make_trade(trade_id="TRD_DUP")
r1 = b3._try_increment_certification_counter(t, True)
r2 = b3._try_increment_certification_counter(t, True)
ok("first True", r1 is True)
ok("second False (duplicate)", r2 is False)
ok("counter == 1", b3.certification_counter == 1)
ok("wins == 1", b3.certification_wins == 1)

print("\n[5] NOT_RECONCILED rejected")
b4 = _bot("NIFTY")
t = make_trade(trade_id="TRD_NR")
r = b4._try_increment_certification_counter(t, False)
ok("rejected", r is False)
ok("counter 0", b4.certification_counter == 0)

print("\n[6] NOT_PAPER rejected")
b5 = _bot("NIFTY")
t = make_trade(trade_id="TRD_NP", execution_mode="LIVE")
r = b5._try_increment_certification_counter(t, True)
ok("rejected", r is False)
ok("counter 0", b5.certification_counter == 0)

print("\n[7] broker_submission=True rejected")
b6 = _bot("NIFTY")
t = make_trade(trade_id="TRD_BS", broker_submission=True)
r = b6._try_increment_certification_counter(t, True)
ok("rejected", r is False)

print("\n[8] live_execution=True rejected")
b7 = _bot("NIFTY")
t = make_trade(trade_id="TRD_LE", live_execution=True)
r = b7._try_increment_certification_counter(t, True)
ok("rejected", r is False)

print("\n[9] certification_eligible=False rejected")
b8 = _bot("NIFTY")
t = make_trade(trade_id="TRD_NE", certification_eligible=False)
r = b8._try_increment_certification_counter(t, True)
ok("rejected", r is False)

print("\n[10] certification_countable=False (AMBIGUOUS) rejected")
b9 = _bot("NIFTY")
t = make_trade(trade_id="TRD_AMB", certification_countable=False,
               first_touch_result="AMBIGUOUS")
r = b9._try_increment_certification_counter(t, True)
ok("rejected", r is False)

print("\n[11] NONE first_touch rejected")
b10 = _bot("NIFTY")
t = make_trade(trade_id="TRD_NONE", first_touch_result="NONE")
r = b10._try_increment_certification_counter(t, True)
ok("rejected", r is False)

print("\n[12] Wrong strategy_version rejected")
b11 = _bot("NIFTY")
t = make_trade(trade_id="TRD_WV", strategy_version="SOMETHING_ELSE")
r = b11._try_increment_certification_counter(t, True)
ok("rejected", r is False)

print("\n[13] Wrong certification_epoch rejected")
b12 = _bot("NIFTY")
t = make_trade(trade_id="TRD_WE", certification_epoch="OTHER_EPOCH")
r = b12._try_increment_certification_counter(t, True)
ok("rejected", r is False)

print("\n[14] NOT_CLOSED rejected")
b13 = _bot("NIFTY")
t = make_trade(trade_id="TRD_OPEN", status="OPEN")
r = b13._try_increment_certification_counter(t, True)
ok("rejected", r is False)

print("\n[15] Net-positive SL_FIRST is still cert loss")
b14 = _bot("NIFTY")
t = make_trade(trade_id="TRD_POSLOSS", first_touch_result="SL_FIRST", net_pnl=500.0)
r = b14._try_increment_certification_counter(t, True)
ok("counted as loss", r is True and b14.certification_losses == 1 and b14.certification_wins == 0)

print("\n[16] Net-negative T1_FIRST is still cert win")
b15 = _bot("NIFTY")
t = make_trade(trade_id="TRD_NEGWIN", first_touch_result="T1_FIRST", net_pnl=-500.0)
r = b15._try_increment_certification_counter(t, True)
ok("counted as win", r is True and b15.certification_wins == 1 and b15.certification_losses == 0)

print("\n[17] Restart preserves counted_trade_ids + counters")
tmp = tempfile.mkdtemp(prefix="r6_persist_")
try:
    b16 = _bot("NIFTY")
    b16.state_file = os.path.join(tmp, "nifty_state.json")
    # ensure new-epoch tagging so reload recognizes fresh state
    b16.strategy_version    = STRATEGY_VERSION
    b16.certification_epoch = CERTIFICATION_EPOCH
    b16.is_legacy_precert   = False
    t = make_trade(trade_id="TRD_RESTART")
    b16._try_increment_certification_counter(t, True)
    b16.save_state()

    b17 = _bot("NIFTY")
    b17.state_file = b16.state_file
    b17.load_state()
    ok("counter preserved", b17.certification_counter == 1)
    ok("wins preserved", b17.certification_wins == 1)
    ok("counted_trade_ids preserved",
       "TRD_RESTART" in b17.counted_trade_ids)
    # Try to re-count the same trade after restart
    r = b17._try_increment_certification_counter(t, True)
    ok("re-count after restart rejected", r is False)
    ok("counter still 1", b17.certification_counter == 1)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n[18] Legacy state loads with cert counters at 0")
tmp = tempfile.mkdtemp(prefix="r6_legacy_")
try:
    p = os.path.join(tmp, "nifty_legacy.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"market": "NIFTY", "current_session": 3, "total_trades": 3}, f)
    b18 = _bot("NIFTY")
    b18.state_file = p
    b18.load_state()
    ok("counter 0 (legacy safe)", b18.certification_counter == 0)
    ok("wins 0", b18.certification_wins == 0)
    ok("counted_trade_ids empty", b18.counted_trade_ids == set())
    ok("marked legacy", b18.is_legacy_precert is True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n[19] Structural - runner loop uses certification_counter")
with open("run_nifty.py", encoding="utf-8") as f:
    n_src = f.read()
with open("run_sensex.py", encoding="utf-8") as f:
    s_src = f.read()
ok("NIFTY loop on cert counter",
   "bot.certification_counter < 100" in n_src)
ok("SENSEX loop on cert counter",
   "bot.certification_counter < 100" in s_src)
ok("NIFTY loop no longer on current_session < 100",
   "bot.current_session < 100" not in n_src)
ok("SENSEX loop no longer on current_session < 100",
   "bot.current_session < 100" not in s_src)

print("\n[20] Structural - save/load persist cert fields")
save_src = inspect.getsource(UnifiedTradingBot.save_state)
load_src = inspect.getsource(UnifiedTradingBot.load_state)
ok("save persists cert counter",
   "'certification_counter': self.certification_counter" in save_src)
ok("save persists counted_trade_ids",
   "'counted_trade_ids':" in save_src)
ok("load restores cert counter",
   "self.certification_counter = int(state.get('certification_counter'" in load_src)
ok("load restores counted_trade_ids",
   "self.counted_trade_ids = set(_cti)" in load_src)

print("\n[21] Structural - /100 increment only in cert helper")
full_src = inspect.getsource(UnifiedTradingBot)
ok("certification_counter += 1 only inside helper",
   full_src.count("self.certification_counter += 1") == 1)
ok("current_session += 1 absent from bot (runner-only)",
   "self.current_session += 1" not in full_src)

print("\n[22] Threshold + Design B unchanged")
ok("T1 15", b.T1_PERCENT == 15)
ok("T2 30", b.T2_PERCENT == 30)
ok("T3 50", b.T3_PERCENT == 50)
ok("SL 5", b.STOP_LOSS_PERCENT == 5)

print("\n[23] Day-1 files unchanged")
for label, active_fname, arch_fname, v1_prefix, day1_prefix in [
    ("nifty_experimental",
     "data/paper_trades/nifty_experimental.json",
     "data/paper_trades/_archived_NS_precert_20260915/nifty_experimental.json",
     "3d8fdbe6", "106e57f3"),
    ("sensex_experimental",
     "data/paper_trades/sensex_experimental.json",
     "data/paper_trades/_archived_NS_precert_20260915/sensex_experimental.json",
     "e58bd4a2", "a1239db0"),
]:
    h_act = sha256(active_fname)
    h_arc = sha256(arch_fname)
    ok(f"{label} unchanged",
       (h_act and h_act.startswith(v1_prefix)) and (h_arc and h_arc.startswith(day1_prefix)),
       f"active={h_act[:8] if h_act else 'MISS'} archive={h_arc[:8] if h_arc else 'MISS'}")

n_pass = sum(1 for _, c in passed if c)
n_fail = sum(1 for _, c in passed if not c)
print()
print(f"R6 FOCUSED TESTS: {n_pass}/{len(passed)} passed")
if n_fail:
    for n, c in passed:
        if not c: print(f"  FAIL: {n}")
    sys.exit(1)
print("R6 FOCUSED TESTS: ALL PASSED")

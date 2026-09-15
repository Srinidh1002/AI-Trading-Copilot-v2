"""R8 focused tests - prediction fingerprint on trade."""
import sys, inspect, tempfile, shutil, os, json, hashlib
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot
from outcome_ledger import OutcomeLedger

passed = []
def ok(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}  {detail}")
    passed.append((name, cond))

def sha256(p):
    if not os.path.exists(p): return None
    with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()

print("=" * 80)
print("R8 FOCUSED TESTS")
print("=" * 80)

print("\n[1] Structural - fingerprint captured after prediction record")
with open("src/target_focused_bot.py", encoding="utf-8") as f:
    full = f.read()
ok("per-cycle reset present",
   "self._last_prediction_fingerprint = None" in full)
ok("capture after record present",
   "self._last_prediction_fingerprint = _record.get('fingerprint')" in full)

print("\n[2] Structural - trade dict carries fingerprint")
src_rss = inspect.getsource(UnifiedTradingBot.run_single_session)
ok("trade dict has prediction_fingerprint",
   "'prediction_fingerprint': getattr(self, '_last_prediction_fingerprint', None)," in src_rss)

print("\n[3] Structural - __init__ initializes attribute")
src_init = inspect.getsource(UnifiedTradingBot.__init__)
ok("_last_prediction_fingerprint initialized",
   "_last_prediction_fingerprint = None" in src_init)

print("\n[4] Runtime - attribute present and defaults None")
b = UnifiedTradingBot("NIFTY")
ok("attribute exists", hasattr(b, "_last_prediction_fingerprint"))
ok("defaults None", b._last_prediction_fingerprint is None)
b._last_prediction_fingerprint = "fp_test_xyz"
ok("accessible after set",
   getattr(b, "_last_prediction_fingerprint", None) == "fp_test_xyz")

print("\n[5] Linkage - outcome ledger preserves fingerprint (R7)")
tmp = tempfile.mkdtemp(prefix="r8_led_")
try:
    led = OutcomeLedger("NIFTY", base_dir=tmp)
    led.record({
        "trade_id": "TRD_TEST", "market": "NIFTY",
        "prediction_fingerprint": "fp_test_xyz",
        "strategy_version": "NS_DESIGN_B_BID_AUTH_V2",
    })
    with open(os.path.join(tmp, "nifty_outcomes.jsonl"), encoding="utf-8") as f:
        rec = json.loads(f.readline())
    ok("outcome preserves prediction_fingerprint",
       rec.get("prediction_fingerprint") == "fp_test_xyz")
    ok("outcome preserves strategy_version",
       rec.get("strategy_version") == "NS_DESIGN_B_BID_AUTH_V2")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n[6] Immutability - Day-1 prediction JSONL unchanged vs archive")
live_h = sha256("data/paper_trades/nifty_predictions.jsonl")
arc_h  = sha256("data/paper_trades/_archived_NS_precert_20260915/nifty_predictions.jsonl")
if live_h and arc_h:
    ok("live == archived", live_h == arc_h, f"{live_h[:16]}... == {arc_h[:16]}...")

n_pass = sum(1 for _, c in passed if c)
n_fail = sum(1 for _, c in passed if not c)
print()
print(f"R8 FOCUSED TESTS: {n_pass}/{len(passed)} passed")
if n_fail:
    for n, c in passed:
        if not c: print(f"  FAIL: {n}")
    sys.exit(1)
print("R8 FOCUSED TESTS: ALL PASSED")

"""R9 focused tests - epoch metadata + legacy-safe load semantics.

Uses tempdir for state files. Does NOT touch data/paper_trades/.
"""
import sys, os, json, tempfile, hashlib, shutil
sys.path.append("src")

from target_focused_bot import UnifiedTradingBot, STRATEGY_VERSION, CERTIFICATION_EPOCH

PASSED = []

def ok(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}  {detail}")
    PASSED.append((name, cond))

def sha256(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

print("=" * 80)
print("R9 FOCUSED TESTS")
print("=" * 80)

# --- Case A: fresh bot has new-epoch metadata ---
print("\n[A] Fresh bot carries new-epoch metadata")
b = UnifiedTradingBot("NIFTY")
ok("strategy_version", b.strategy_version == STRATEGY_VERSION,
   f"{b.strategy_version!r}")
ok("certification_epoch", b.certification_epoch == CERTIFICATION_EPOCH,
   f"{b.certification_epoch!r}")
ok("is_legacy_precert False", b.is_legacy_precert is False)

# --- Case B: save + reload round-trips both keys ---
print("\n[B] Save + reload preserves epoch metadata")
tmpdir = tempfile.mkdtemp(prefix="r9_test_")
try:
    b.state_file = os.path.join(tmpdir, "nifty_state.json")
    b.save_state()
    with open(b.state_file, encoding="utf-8") as f:
        disk = json.load(f)
    ok("file has strategy_version",
       disk.get("strategy_version") == STRATEGY_VERSION,
       f"{disk.get('strategy_version')!r}")
    ok("file has certification_epoch",
       disk.get("certification_epoch") == CERTIFICATION_EPOCH,
       f"{disk.get('certification_epoch')!r}")

    b2 = UnifiedTradingBot("NIFTY")
    b2.state_file = b.state_file
    b2.load_state()
    ok("reload strategy_version", b2.strategy_version == STRATEGY_VERSION)
    ok("reload certification_epoch", b2.certification_epoch == CERTIFICATION_EPOCH)
    ok("reload is_legacy_precert False", b2.is_legacy_precert is False)
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# --- Case C: legacy state without epoch fields is NOT relabeled ---
print("\n[C] Legacy state (no epoch fields) loads as PRE_CERT, file unchanged")
tmpdir = tempfile.mkdtemp(prefix="r9_test_legacy_")
try:
    legacy_path = os.path.join(tmpdir, "nifty_legacy.json")
    legacy_state = {
        "market": "NIFTY",
        "timestamp": "2026-09-15T15:27:41.301521",
        "current_session": 3,
        "total_trades": 3,
        "total_pnl": -833.85,
        # NOTE: no strategy_version, no certification_epoch
    }
    with open(legacy_path, "w", encoding="utf-8") as f:
        json.dump(legacy_state, f, indent=2)
    before = sha256(legacy_path)

    b3 = UnifiedTradingBot("NIFTY")
    b3.state_file = legacy_path
    b3.load_state()

    ok("legacy strategy_version is None", b3.strategy_version is None,
       f"{b3.strategy_version!r}")
    ok("legacy certification_epoch is None", b3.certification_epoch is None,
       f"{b3.certification_epoch!r}")
    ok("legacy is_legacy_precert True", b3.is_legacy_precert is True)
    ok("legacy counter preserved", b3.current_session == 3)
    ok("legacy total_pnl preserved", b3.total_pnl == -833.85)

    after = sha256(legacy_path)
    ok("legacy file unchanged by load_state", before == after,
       f"{before[:16]}... == {after[:16]}...")
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# --- Case D: trade dict source carries both keys ---
print("\n[D] Trade dict source carries both metadata keys")
with open("src/target_focused_bot.py", encoding="utf-8") as f:
    bot_src = f.read()
ok("trade dict has strategy_version",
   "'strategy_version':    self.strategy_version," in bot_src
   or "'strategy_version': self.strategy_version," in bot_src)
ok("trade dict has certification_epoch",
   "'certification_epoch': self.certification_epoch," in bot_src)

# --- Case E: constants are exact strings ---
print("\n[E] Constants match approved values")
ok("STRATEGY_VERSION exact",
   STRATEGY_VERSION == "NS_DESIGN_B_BID_AUTH_V2",
   f"{STRATEGY_VERSION!r}")
ok("CERTIFICATION_EPOCH exact",
   CERTIFICATION_EPOCH == "NS_CERT_20260916_V1",
   f"{CERTIFICATION_EPOCH!r}")

# --- Summary ---
n_pass = sum(1 for _, c in PASSED if c)
n_fail = sum(1 for _, c in PASSED if not c)
print()
print(f"R9 FOCUSED TESTS: {n_pass}/{len(PASSED)} passed")
if n_fail:
    print("FAILURES:")
    for n, c in PASSED:
        if not c:
            print(f"  - {n}")
    sys.exit(1)
print("R9 FOCUSED TESTS: ALL PASSED")

"""R7 focused tests - outcome ledger schema extension.

Uses tempdir. Does NOT touch data/paper_trades/.
"""
import sys, os, json, tempfile, hashlib, shutil, ast
sys.path.append("src")

from outcome_ledger import OutcomeLedger

PASSED = []

def ok(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}  {detail}")
    PASSED.append((name, cond))

def sha256(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

print("=" * 80)
print("R7 FOCUSED TESTS — outcome ledger schema")
print("=" * 80)

# --- Test 1: legacy trade dict still serializes ---
print("\n[1] Legacy trade dict serializes successfully")
tmpdir = tempfile.mkdtemp(prefix="r7_legacy_")
try:
    ledger = OutcomeLedger("NIFTY", base_dir=tmpdir)
    legacy_trade = {
        "trade_id": "TRD_LEGACY", "market": "NIFTY",
        "symbol": "NIFTY15SEP2623300PE", "type": "PE", "strike": 23300,
        "signal": "BUY", "entry": 61.4, "exit_price": 58.06,
        "entry_time": "2026-09-15 13:32:12", "exit_time": "2026-09-15 13:35:00",
        "exit_reason": "STOP_LOSS", "quantity": 65, "lot_size": 65,
        "gross_pnl": -217.1, "net_pnl": -271.37, "net_pnl_pct": -6.8,
        "costs_total": 54.27, "mfe": 1.5, "mae": -3.25,
        "peak_pnl_pct": 2.44, "trough_pnl_pct": -5.29,
        "rank_score": 97.0, "execution_mode": "PAPER",
        "broker_submission": False, "live_execution": False,
        "certification_eligible": True,
    }
    ok("legacy record returns True", ledger.record(legacy_trade) is True)
    p = os.path.join(tmpdir, "nifty_outcomes.jsonl")
    ok("file created", os.path.exists(p))
    with open(p, encoding="utf-8") as f:
        lines = f.readlines()
    ok("one line written", len(lines) == 1)
    rec = json.loads(lines[0])
    ok("legacy trade_id preserved", rec["trade_id"] == "TRD_LEGACY")
    ok("legacy net_pnl preserved", rec["net_pnl"] == -271.37)
    ok("legacy entry preserved", rec["entry"] == 61.4)
    ok("legacy exit_reason preserved", rec["exit_reason"] == "STOP_LOSS")
    # New fields should be None since trade didn't provide them
    ok("new field strategy_version is None", rec.get("strategy_version") is None)
    ok("new field first_touch_result is None", rec.get("first_touch_result") is None)
    ok("new field certification_win is None", rec.get("certification_win") is None)
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# --- Test 2: new-epoch trade with all fields preserved exactly ---
print("\n[2] New-epoch trade preserves all new fields exactly")
tmpdir = tempfile.mkdtemp(prefix="r7_newepoch_")
try:
    ledger = OutcomeLedger("NIFTY", base_dir=tmpdir)
    new_trade = {
        "trade_id": "TRD_NEW_EPOCH",
        "market": "NIFTY", "symbol": "NIFTY16SEP2623400PE",
        "type": "PE", "strike": 23400, "signal": "BUY",
        "entry": 100.0, "exit_price": 110.0,
        "entry_time": "2026-09-16 09:20:00", "exit_time": "2026-09-16 09:40:00",
        "exit_reason": "TRAIL_STOP", "quantity": 65, "lot_size": 65,
        "gross_pnl": 650.0, "net_pnl": 595.0, "net_pnl_pct": 9.15,
        "costs_total": 55.0, "mfe": 20.0, "mae": -5.0,
        "peak_pnl_pct": 20.0, "trough_pnl_pct": -5.0, "rank_score": 96.0,
        "execution_mode": "PAPER", "broker_submission": False,
        "live_execution": False, "certification_eligible": True,

        # R9 metadata
        "strategy_version":     "NS_DESIGN_B_BID_AUTH_V2",
        "certification_epoch":  "NS_CERT_20260916_V2",
        # R8 linkage
        "prediction_fingerprint": "fp_abc123",
        # entry/exit execution
        "entry_bid": 99.85, "entry_ask": 99.95, "entry_ltp": 99.90,
        "exit_bid": 110.10,
        # milestones
        "t1_hit": True, "t2_hit": False,
        # first-touch timestamps
        "t1_first_seen_at": "2026-09-16T09:31:12.123+05:30",
        "t2_first_seen_at": None,
        "t3_first_seen_at": None,
        "sl_first_seen_at": None,
        # first-touch bids
        "t1_bid": 115.00, "t2_bid": None, "t3_bid": None, "sl_bid": None,
        # ordering
        "first_touch_result": "T1_FIRST",
        # cert outcome
        "certification_win": True, "certification_loss": False,
        "certification_countable": True,
        # trail evidence
        "trail_stop": 118.00, "peak_bid": 125.00, "trough_bid": 95.00,
        # gap evidence
        "monitoring_gap_count": 0, "monitoring_gap_started_at": None,
        "evidence_ambiguous": False,
    }
    ledger.record(new_trade)
    p = os.path.join(tmpdir, "nifty_outcomes.jsonl")
    with open(p, encoding="utf-8") as f:
        rec = json.loads(f.readline())

    for fld, expected in [
        ("strategy_version", "NS_DESIGN_B_BID_AUTH_V2"),
        ("certification_epoch", "NS_CERT_20260916_V2"),
        ("prediction_fingerprint", "fp_abc123"),
        ("entry_bid", 99.85), ("entry_ask", 99.95), ("entry_ltp", 99.90),
        ("exit_bid", 110.10),
        ("t1_hit", True), ("t2_hit", False),
        ("t1_first_seen_at", "2026-09-16T09:31:12.123+05:30"),
        ("t1_bid", 115.00),
        ("first_touch_result", "T1_FIRST"),
        ("certification_win", True), ("certification_loss", False),
        ("certification_countable", True),
        ("trail_stop", 118.00), ("peak_bid", 125.00), ("trough_bid", 95.00),
        ("monitoring_gap_count", 0),
        ("evidence_ambiguous", False),
    ]:
        ok(f"{fld} preserved", rec.get(fld) == expected, f"{rec.get(fld)!r}")
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# --- Test 3: missing new fields don't crash ---
print("\n[3] Missing new fields do not crash serialization")
tmpdir = tempfile.mkdtemp(prefix="r7_missing_")
try:
    ledger = OutcomeLedger("NIFTY", base_dir=tmpdir)
    minimal = {"trade_id": "TRD_MIN", "market": "NIFTY"}
    ok("minimal record returns True", ledger.record(minimal) is True)
    p = os.path.join(tmpdir, "nifty_outcomes.jsonl")
    with open(p, encoding="utf-8") as f:
        rec = json.loads(f.readline())
    ok("minimal record parses", isinstance(rec, dict))
    ok("missing new field is None", rec.get("t1_hit") is None)
    ok("missing new field is None (2)", rec.get("certification_win") is None)
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# --- Test 4: JSONL stays one object per line ---
print("\n[4] JSONL is one valid JSON object per line")
tmpdir = tempfile.mkdtemp(prefix="r7_jsonl_")
try:
    ledger = OutcomeLedger("NIFTY", base_dir=tmpdir)
    for i in range(3):
        ledger.record({"trade_id": f"TRD_{i}", "market": "NIFTY"})
    p = os.path.join(tmpdir, "nifty_outcomes.jsonl")
    with open(p, encoding="utf-8") as f:
        lines = f.readlines()
    ok("3 lines written", len(lines) == 3)
    ok("every line parses", all(isinstance(json.loads(l), dict) for l in lines))
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# --- Test 5: import-time side-effect check ---
print("\n[5] Importing module does not mutate existing files")
real_p = "data/paper_trades/nifty_outcomes.jsonl"
if os.path.exists(real_p):
    before = sha256(real_p)
    import importlib, outcome_ledger
    importlib.reload(outcome_ledger)
    after = sha256(real_p)
    ok("nifty_outcomes.jsonl unchanged by import", before == after,
       f"{before[:16]}... == {after[:16]}...")
else:
    ok("nifty_outcomes.jsonl missing (skip)", True, "n/a")

real_s = "data/paper_trades/sensex_outcomes.jsonl"
if os.path.exists(real_s):
    before = sha256(real_s)
    importlib.reload(outcome_ledger)
    after = sha256(real_s)
    ok("sensex_outcomes.jsonl unchanged by import", before == after,
       f"{before[:16]}... == {after[:16]}...")
else:
    ok("sensex_outcomes.jsonl missing (skip)", True, "n/a")

# --- Test 6: source has no derivation of certification_win from net_pnl ---
print("\n[6] Source has no derivation of certification_win from net_pnl")
with open("src/outcome_ledger.py", encoding="utf-8") as f:
    src = f.read()
# rule: every cert field must be assignment from trade.get(...)
derivation_ok = True
for fld in ("certification_win", "certification_loss",
            "certification_countable", "first_touch_result",
            "t1_hit", "t2_hit"):
    # look for the assignment line
    import re
    m = re.search(rf'"{fld}"\s*:\s*([^,\n]+)', src)
    if not m:
        derivation_ok = False
        print(f"    MISSING assignment for {fld}")
        continue
    rhs = m.group(1).strip()
    if not rhs.startswith("trade.get("):
        derivation_ok = False
        print(f"    {fld} RHS is not trade.get(...): {rhs}")
ok("all cert fields assigned from trade.get only", derivation_ok)

# Explicit check: no reference to net_pnl inside a cert_win assignment
bad_pattern_present = False
for line in src.splitlines():
    if "certification_win" in line and "net_pnl" in line:
        bad_pattern_present = True
ok("no cert_win <- net_pnl derivation line", not bad_pattern_present)

# --- Summary ---
n_pass = sum(1 for _, c in PASSED if c)
n_fail = sum(1 for _, c in PASSED if not c)
print()
print(f"R7 FOCUSED TESTS: {n_pass}/{len(PASSED)} passed")
if n_fail:
    print("FAILURES:")
    for n, c in PASSED:
        if not c:
            print(f"  - {n}")
    sys.exit(1)
print("R7 FOCUSED TESTS: ALL PASSED")

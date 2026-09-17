import sys, json, os, tempfile
sys.path.append("src")
from outcome_ledger import OutcomeLedger

# Test in a temp dir so we don't touch real ledgers
tmp = tempfile.mkdtemp()
ledger = OutcomeLedger("NIFTY", base_dir=tmp)

fake_trade = {
    "trade_id": "TEST_D3",
    "symbol": "NIFTY25SEP24000CE",
    "type": "CE", "strike": 24000, "signal": "BUY",
    "entry": 100.0, "exit_price": 115.0,
    "entry_time": "2026-09-15T10:00:00", "exit_time": "2026-09-15T10:15:00",
    "exit_reason": "T1_15%", "quantity": 75, "lot_size": 75,
    "gross_pnl": 1125.0, "net_pnl": 1100.0, "net_pnl_pct": 14.67,
    "costs_total": 25.0,
    "execution_mode": "PAPER",
    "broker_submission": False,
    "live_execution": False,
    "certification_eligible": True,
}
ledger.record(fake_trade)

# Read back
p = os.path.join(tmp, "nifty_outcomes.jsonl")
with open(p) as f:
    rec = json.loads(f.readline())

for k in ("execution_mode", "broker_submission", "live_execution", "certification_eligible"):
    print(f"  {k} = {rec.get(k)!r}")

assert rec["execution_mode"] == "PAPER"
assert rec["broker_submission"] is False
assert rec["live_execution"] is False
assert rec["certification_eligible"] is True
print("D3 verification PASSED — temp dir cleaned")
import shutil
shutil.rmtree(tmp)

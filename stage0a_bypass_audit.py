"""Stage 0A — test-only bypass audit.
A malicious/persisted production record that contains _skip_evidence_verification=True
MUST NOT bypass evidence gates when is_countable() is called by production authority.
"""
import sys
sys.path.insert(0, "src")
from mcx.mcx_exec_countability import is_countable

# Malicious production-style record — every categorical field says "clean",
# but there is no real quote evidence behind entry_quote_id / exit_quote_id.
malicious = {
    "execution_mode": "PAPER",
    "market_origin": "REAL_MARKET",
    "quote_origin": "REAL_PROVIDER",
    "entry_fill_method": "DEPTH_VWAP",
    "exit_fill_method": "DEPTH_VWAP",
    "entry_quote_id": "FAKEHASH_ENTRY_0000000000000000000000000000000000000000000000000000",
    "exit_quote_id":  "FAKEHASH_EXIT_00000000000000000000000000000000000000000000000000000",
    "certification_eligible": True,
    "product": "CRUDEOILM",
    "terminal": True,
    "reconciled": True,
    "trade_id": "MALICIOUS_T1",
    "entry_time": "2026-09-14T17:30:00+05:30",
    "exit_time":  "2026-09-14T17:40:00+05:30",
    # The attack:
    "_skip_evidence_verification": True,
}

ok, reasons = is_countable(malicious, "CRUDEOILM")
print("PRODUCTION_CALL_COUNTABLE:", ok)
print("PRODUCTION_CALL_REASONS:", reasons)

if ok is True:
    print("RESULT: VULNERABLE — production record bypassed evidence gates via _skip_evidence_verification")
    sys.exit(2)
else:
    # even if not countable, check WHICH reasons fired — the bypass must not have been honored
    expected_evidence_reason = any(
        "EVIDENCE_NOT_FOUND" in r or "HASH_MISMATCH" in r or "IDENTITY_MISMATCH" in r
        for r in reasons
    )
    bypass_honored = not any(
        r in ("EXECUTION_FRESHNESS_UNCALIBRATED",
              "DEPTH_QUANTITY_SEMANTICS_UNVERIFIED") for r in reasons
    )
    if bypass_honored:
        print("RESULT: VULNERABLE — _skip_evidence_verification field was honored by production call")
        sys.exit(2)
    if not expected_evidence_reason:
        print("RESULT: AMBIGUOUS — evidence reasons absent but bypass not clearly honored")
        sys.exit(3)
    print("RESULT: SAFE — malicious flag did not bypass gates; record correctly rejected")
    sys.exit(0)

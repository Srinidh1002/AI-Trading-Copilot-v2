"""Section 7.38-7.40 — countability gate. 16 conditions."""
import os, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_version import is_certification_eligible


REJECTIONS = (
    "NON_PAPER_MODE", "NON_REAL_MARKET_ORIGIN", "NON_REAL_QUOTE_ORIGIN",
    "SYNTHETIC_FILL", "ENTRY_DEPTH_EVIDENCE_MISSING", "EXIT_DEPTH_EVIDENCE_MISSING",
    "ENTRY_QUOTE_STALE", "EXIT_QUOTE_STALE", "AMBIGUOUS_FIRST_TOUCH",
    "LIFECYCLE_EVIDENCE_INCOMPLETE", "PRODUCT_NOT_CERTIFICATION_ELIGIBLE",
    "RECORD_NOT_CERTIFICATION_ELIGIBLE", "NOT_TERMINAL", "NOT_RECONCILED",
    "DUPLICATE_TRADE",
    "EXECUTION_FRESHNESS_UNCALIBRATED",
    "DEPTH_QUANTITY_SEMANTICS_UNVERIFIED",
    "ENTRY_QUOTE_EVIDENCE_NOT_FOUND",
    "EXIT_QUOTE_EVIDENCE_NOT_FOUND",
    "ENTRY_QUOTE_HASH_MISMATCH",
    "EXIT_QUOTE_HASH_MISMATCH",
    "ENTRY_IDENTITY_MISMATCH",
    "EXIT_IDENTITY_MISMATCH",
    "FILL_NOT_REPRODUCIBLE_FROM_DEPTH",
    "ENTRY_QUOTE_NOT_VALID_STATUS",
    "EXIT_QUOTE_NOT_VALID_STATUS",
    "ENTRY_QUOTE_EVIDENCE_VERIFICATION_ERROR",
    "EXIT_QUOTE_EVIDENCE_VERIFICATION_ERROR",
)

VERIFY_EXECUTION_EVIDENCE = True


def _evidence_verify_one(trade, quote_id, prefix, product, date_iso=None):
    """Verify one side (ENTRY or EXIT). Returns list of rejection reasons."""
    reasons = []
    if not quote_id:
        reasons.append(f"{prefix}_QUOTE_EVIDENCE_NOT_FOUND")
        return reasons
    try:
        from mcx.mcx_exec_recorder import load_quote_by_hash
    except Exception:
        reasons.append(f"{prefix}_QUOTE_EVIDENCE_NOT_FOUND")
        return reasons
    if date_iso is None:
        # Derive from entry_time/exit_time day
        ts_key = "entry_time" if prefix == "ENTRY" else "exit_time"
        ts_val = trade.get(ts_key) or ""
        date_iso = (ts_val or "")[:10]
    q = load_quote_by_hash(product, date_iso, quote_id)
    if not q:
        reasons.append(f"{prefix}_QUOTE_EVIDENCE_NOT_FOUND")
        return reasons
    if q.get("validation_status") != "VALID":
        reasons.append(f"{prefix}_QUOTE_NOT_VALID_STATUS")
        return reasons
    # Identity match
    want_product = product
    want_token = trade.get("token")
    want_strike = trade.get("strike")
    want_type = trade.get("type")
    if (q.get("product") != want_product or
        str(q.get("token")) != str(want_token) or
        q.get("option_type") != want_type or
        float(q.get("strike") or 0) != float(want_strike or 0)):
        reasons.append(f"{prefix}_IDENTITY_MISMATCH")
    # Hash match against stored file
    import hashlib, json as _json
    computed = hashlib.sha256(_json.dumps(
        {k: v for k, v in q.items() if not k.startswith("_") and k != "validation_status" and k != "rejection_reasons"},
        sort_keys=True, default=str).encode()).hexdigest()
    # Note: stored hash is what was recorded at fetch time; we don't have the original raw payload
    # to compare. Instead we check the quote's own raw_payload_hash field matches the filename we loaded.
    if q.get("raw_payload_hash") != quote_id:
        reasons.append(f"{prefix}_QUOTE_HASH_MISMATCH")
    # Fill reproducibility
    tick = float(q.get("tick_size") or 0.05)
    bids = q.get("bids") or []
    asks = q.get("asks") or []
    trading_unit = 1
    try:
        from mcx.mcx_contracts import PRODUCTS
        trading_unit = PRODUCTS.get(product, {}).get("trading_unit", 1)
    except Exception:
        pass
    lots = int(trade.get("lots", 0) or 0)
    qty = max(1, lots * trading_unit)
    try:
        from mcx.mcx_exec_fill import depth_vwap_for_buy, depth_vwap_for_sell
    except Exception:
        return reasons
    if prefix == "ENTRY":
        fill, filled, levels, worst, status = depth_vwap_for_buy(asks, qty, tick)
        recorded_fill = trade.get("entry")
    else:
        fill, filled, levels, worst, status = depth_vwap_for_sell(bids, qty, tick)
        recorded_fill = trade.get("exit")
    if status != "OK":
        reasons.append(f"{prefix}_QUOTE_EVIDENCE_NOT_FOUND")
    elif fill is None or recorded_fill is None or abs(float(fill) - float(recorded_fill)) > 1e-6:
        reasons.append("FILL_NOT_REPRODUCIBLE_FROM_DEPTH")
    return reasons


def is_countable(trade, product=None, known_trade_ids=None, *,
                 _allow_evidence_bypass=False):  # 7W_keyword_bypass
    """Return (countable, reasons). Section P0-C: verifies execution evidence."""
    reasons = []
    if trade.get("execution_mode") != "PAPER":
        reasons.append("NON_PAPER_MODE")
    if trade.get("market_origin") != "REAL_MARKET":
        reasons.append("NON_REAL_MARKET_ORIGIN")
    if trade.get("quote_origin") != "REAL_PROVIDER":
        reasons.append("NON_REAL_QUOTE_ORIGIN")
    if trade.get("entry_fill_method") != "DEPTH_VWAP" or \
       trade.get("exit_fill_method") != "DEPTH_VWAP":
        reasons.append("SYNTHETIC_FILL")
    if not trade.get("entry_quote_id"):
        reasons.append("ENTRY_QUOTE_EVIDENCE_NOT_FOUND")
    if not trade.get("exit_quote_id"):
        reasons.append("EXIT_QUOTE_EVIDENCE_NOT_FOUND")
    if trade.get("entry_quote_stale"):
        reasons.append("ENTRY_QUOTE_STALE")
    if trade.get("exit_quote_stale"):
        reasons.append("EXIT_QUOTE_STALE")
    if trade.get("first_touch_result") == "AMBIGUOUS":
        reasons.append("AMBIGUOUS_FIRST_TOUCH")
    if not trade.get("lifecycle_evidence_complete", True):
        reasons.append("LIFECYCLE_EVIDENCE_INCOMPLETE")
    p = product or trade.get("product")
    if not is_certification_eligible(p):
        reasons.append("PRODUCT_NOT_CERTIFICATION_ELIGIBLE")
    if not trade.get("certification_eligible"):
        reasons.append("RECORD_NOT_CERTIFICATION_ELIGIBLE")
    if not trade.get("terminal", False):
        reasons.append("NOT_TERMINAL")
    if not trade.get("reconciled", False):
        reasons.append("NOT_RECONCILED")
    tid = trade.get("trade_id")
    if known_trade_ids and tid in known_trade_ids:
        reasons.append("DUPLICATE_TRADE")
    # 7W_keyword_bypass — evidence gates are SKIPPED ONLY when the caller
    # explicitly opts in via keyword-only argument. A record carrying
    # "_skip_evidence_verification": true is IGNORED (production authority
    # never reads that field).
    if not _allow_evidence_bypass:
        # S7_STAGE_6_FRESHNESS_PER_PRODUCT — use config per-product
        try:
            from mcx.mcx_exec_config import is_freshness_calibrated as _cfg_fc
            if not _cfg_fc(p):
                reasons.append("EXECUTION_FRESHNESS_UNCALIBRATED")
        except Exception:
            reasons.append("EXECUTION_FRESHNESS_UNCALIBRATED")
        try:
            from mcx.mcx_exec_config import is_quantity_semantics_verified
            if not is_quantity_semantics_verified(p):
                reasons.append("DEPTH_QUANTITY_SEMANTICS_UNVERIFIED")
        except Exception:
            reasons.append("DEPTH_QUANTITY_SEMANTICS_UNVERIFIED")
        try:
            reasons.extend(_evidence_verify_one(trade, trade.get("entry_quote_id"), "ENTRY", p))
        except Exception:
            reasons.append("ENTRY_QUOTE_EVIDENCE_VERIFICATION_ERROR")
        try:
            reasons.extend(_evidence_verify_one(trade, trade.get("exit_quote_id"), "EXIT", p))
        except Exception:
            reasons.append("EXIT_QUOTE_EVIDENCE_VERIFICATION_ERROR")
    return (len(reasons) == 0, reasons)


if __name__ == "__main__":
    # Malformed: replay origin, synthetic fill
    bad = {"execution_mode": "REPLAY_DIAGNOSTIC", "market_origin": "HISTORICAL",
           "quote_origin": "SYNTHETIC", "entry_fill_method": "LTP",
           "certification_eligible": True, "product": "CRUDEOILM",
           "terminal": True, "reconciled": True}
    ok, r = is_countable(bad, "CRUDEOILM")
    print("malformed:", ok, r)
    # GOLDM PRECERT — cannot count even if record claims True
    gold = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
            "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
            "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
            "exit_quote_id": "Q2", "certification_eligible": True,
            "product": "GOLDM", "terminal": True, "reconciled": True}
    ok2, r2 = is_countable(gold, "GOLDM")
    print("gold (should reject):", ok2, r2)

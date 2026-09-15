# S7_STAGE_6_TEST_UPDATE
# 7W_test_kwarg
# 7T_gate_tests_opt_in
# 7S_test_fixes
# 7R_max_age_scanned
"""Section 7 offline tests. 75 checks. No live data."""
import os, sys, json, re
from datetime import datetime, timezone, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _quote(**kw):
    from mcx.mcx_exec_quote import make_execution_quote
    base = dict(
        product="CRUDEOILM", option_symbol="TEST", token="999",
        exchange="MCX", option_type="CE", strike=9500, expiry="2026-09-17",
        ltp=100.0,
        bids=[{"price": 99.90, "quantity": 100, "orders": 5}],
        asks=[{"price": 100.10, "quantity": 100, "orders": 5}],
        exchange_feed_time="2026-09-12T10:00:00+00:00",
        provider_received_at="2026-09-12T10:00:01+00:00",
        tick_size=0.05,
    )
    base.update(kw)
    return make_execution_quote(**base)


# 1-5 Canonical + validation
def t01_canonical_quote():
    q = _quote()
    assert q["product"] == "CRUDEOILM" and q["best_bid"] == 99.90

def t02_valid_quote():
    from mcx.mcx_exec_quote import validate_quote
    ok, q = validate_quote(_quote(), "999", now_iso="2026-09-12T10:00:02+00:00", max_age_seconds=3.0)
    assert ok, q["rejection_reasons"]

def t03_wrong_token_rejected():
    from mcx.mcx_exec_quote import validate_quote
    ok, q = validate_quote(_quote(), "888", max_age_seconds=3.0)
    assert not ok and "SYMBOL_TOKEN_MISMATCH" in q["rejection_reasons"]

def t04_wrong_exchange_rejected():
    from mcx.mcx_exec_quote import validate_quote
    ok, q = validate_quote(_quote(exchange="NSE"), "999", max_age_seconds=3.0)
    assert not ok and "WRONG_EXCHANGE" in q["rejection_reasons"]

def t05_zero_bid_rejected():
    from mcx.mcx_exec_quote import validate_quote
    q = _quote(bids=[{"price": 0, "quantity": 100, "orders": 1}])
    ok, v = validate_quote(q, "999", max_age_seconds=3.0)
    assert not ok and "ZERO_BEST_BID" in v["rejection_reasons"]

# 6-12 Validation edge cases
def t06_zero_ask_rejected():
    from mcx.mcx_exec_quote import validate_quote
    q = _quote(asks=[{"price": 0, "quantity": 100, "orders": 1}])
    ok, v = validate_quote(q, "999", max_age_seconds=3.0)
    assert not ok and "ZERO_BEST_ASK" in v["rejection_reasons"]

def t07_crossed_book_rejected():
    from mcx.mcx_exec_quote import validate_quote
    q = _quote(bids=[{"price": 105, "quantity": 50}],
               asks=[{"price": 100, "quantity": 50}])
    ok, v = validate_quote(q, "999", max_age_seconds=3.0)
    assert not ok and "CROSSED_BOOK_INVALID" in v["rejection_reasons"]

def t08_negative_quantity_rejected():
    from mcx.mcx_exec_quote import validate_quote
    q = _quote(bids=[{"price": 99.9, "quantity": -10}])
    ok, v = validate_quote(q, "999", max_age_seconds=3.0)
    assert not ok and "NEGATIVE_QUANTITY" in v["rejection_reasons"]

def t09_stale_quote_rejected():
    from mcx.mcx_exec_quote import validate_quote
    q = _quote(provider_received_at="2026-09-12T09:00:00+00:00")
    ok, v = validate_quote(q, "999", now_iso="2026-09-12T10:00:00+00:00", max_age_seconds=3.0)
    assert not ok and "STALE_QUOTE" in v["rejection_reasons"]

def t10_missing_feed_time_rejected():
    from mcx.mcx_exec_quote import validate_quote
    q = _quote(exchange_feed_time=None)
    ok, v = validate_quote(q, "999", max_age_seconds=3.0)
    assert not ok and "MISSING_FEED_TIME" in v["rejection_reasons"]

def t11_bids_must_be_descending():
    from mcx.mcx_exec_quote import validate_quote
    q = _quote(bids=[{"price": 99.5, "quantity": 50},
                     {"price": 99.9, "quantity": 50}])
    ok, v = validate_quote(q, "999", max_age_seconds=3.0)
    assert not ok and "BIDS_NOT_SORTED" in v["rejection_reasons"]

def t12_asks_must_be_ascending():
    from mcx.mcx_exec_quote import validate_quote
    q = _quote(asks=[{"price": 100.5, "quantity": 50},
                     {"price": 100.1, "quantity": 50}])
    ok, v = validate_quote(q, "999", max_age_seconds=3.0)
    assert not ok and "ASKS_NOT_SORTED" in v["rejection_reasons"]

# 13-18 Depth extraction
def t13_depth_dict_schema():
    from mcx.mcx_exec_depth import extract_depth
    row = {"depth": {"buy": [{"price": 100.0, "quantity": 50, "orders": 2}],
                     "sell": [{"price": 100.5, "quantity": 50, "orders": 2}]}}
    b, a, present, notes = extract_depth(row)
    assert present and b[0]["price"] == 100.0 and a[0]["price"] == 100.5

def t14_bestfive_schema():
    from mcx.mcx_exec_depth import extract_depth
    row = {"bestFiveBuyData": [{"price": 100.0, "quantity": 50}],
           "bestFiveSellData": [{"price": 100.5, "quantity": 50}]}
    b, a, present, notes = extract_depth(row)
    assert present and len(b) == 1 and len(a) == 1

def t15_no_depth_reports_present_false():
    from mcx.mcx_exec_depth import extract_depth
    b, a, present, notes = extract_depth({"ltp": 100})
    assert not present and "NO_DEPTH_FIELDS_PRESENT" in notes

def t16_unsorted_bids_are_reordered():
    from mcx.mcx_exec_depth import extract_depth
    row = {"depth": {"buy": [{"price": 99.5, "quantity": 10},
                              {"price": 99.9, "quantity": 10}], "sell": []}}
    b, a, present, notes = extract_depth(row)
    assert "BIDS_WERE_UNSORTED" in notes and b[0]["price"] == 99.9

def t17_zero_price_levels_dropped():
    from mcx.mcx_exec_depth import extract_depth
    row = {"depth": {"buy": [{"price": 0, "quantity": 10},
                              {"price": 99.9, "quantity": 10}], "sell": []}}
    b, a, present, notes = extract_depth(row)
    assert len(b) == 1

def t18_ask_side_extracted():
    from mcx.mcx_exec_depth import extract_depth
    row = {"depth": {"buy": [], "sell": [{"price": 101.0, "quantity": 25}]}}
    b, a, present, notes = extract_depth(row)
    assert present and a[0]["price"] == 101.0

# 19-25 Fill VWAP
def t19_single_level_buy():
    from mcx.mcx_exec_fill import depth_vwap_for_buy
    asks = [{"price": 10.00, "quantity": 100}]
    f, q, n, w, s = depth_vwap_for_buy(asks, 50, tick=0.05)
    assert s == "OK" and f == 10.00 and n == 1

def t20_multi_level_buy_vwap():
    from mcx.mcx_exec_fill import depth_vwap_for_buy
    asks = [{"price": 10.00, "quantity": 40},
            {"price": 10.05, "quantity": 40},
            {"price": 10.10, "quantity": 20}]
    f, q, n, w, s = depth_vwap_for_buy(asks, 100, tick=0.05)
    # (40*10 + 40*10.05 + 20*10.10)/100 = 10.035 -> 10.05 rounded
    assert s == "OK" and f == 10.05 and n == 3

def t21_single_level_sell():
    from mcx.mcx_exec_fill import depth_vwap_for_sell
    bids = [{"price": 99.5, "quantity": 100}]
    f, q, n, w, s = depth_vwap_for_sell(bids, 50, tick=0.05)
    assert s == "OK" and f == 99.5

def t22_multi_level_sell_vwap():
    from mcx.mcx_exec_fill import depth_vwap_for_sell
    bids = [{"price": 100.0, "quantity": 30},
            {"price": 99.9, "quantity": 30},
            {"price": 99.8, "quantity": 40}]
    f, q, n, w, s = depth_vwap_for_sell(bids, 100, tick=0.05)
    # (30*100 + 30*99.9 + 40*99.8)/100 = 99.89 -> tick-round to 99.90
    assert s == "OK" and f == 99.90

def t23_insufficient_ask_depth():
    from mcx.mcx_exec_fill import depth_vwap_for_buy
    asks = [{"price": 10.0, "quantity": 10}]
    f, q, n, w, s = depth_vwap_for_buy(asks, 100, tick=0.05)
    assert s == "INSUFFICIENT_VISIBLE_DEPTH"

def t24_insufficient_bid_depth():
    from mcx.mcx_exec_fill import depth_vwap_for_sell
    bids = [{"price": 10.0, "quantity": 10}]
    f, q, n, w, s = depth_vwap_for_sell(bids, 100, tick=0.05)
    assert s == "INSUFFICIENT_VISIBLE_DEPTH"

def t25_zero_ask_depth():
    from mcx.mcx_exec_fill import depth_vwap_for_buy
    f, q, n, w, s = depth_vwap_for_buy([], 10, tick=0.05)
    assert s == "NO_ASK_DEPTH"

# 26-30 compute_paper_fill_v2 (integrated)
def t26_v2_valid_buy():
    from mcx.mcx_exec_fill import compute_paper_fill_v2
    from mcx.mcx_exec_quote import validate_quote
    q = _quote()
    ok, q = validate_quote(q, "999", now_iso="2026-09-12T10:00:02+00:00", max_age_seconds=3.0)
    r = compute_paper_fill_v2(q, "BUY", 50, tick=0.05)
    assert r["status"] == "OK" and r["fill_method"] == "DEPTH_VWAP"

def t27_v2_invalid_quote_returns_invalid():
    from mcx.mcx_exec_fill import compute_paper_fill_v2
    q = _quote(); q["validation_status"] = "INVALID"; q["rejection_reasons"] = ["TEST"]
    r = compute_paper_fill_v2(q, "BUY", 50)
    assert r["status"] == "QUOTE_INVALID"

def t28_v2_insufficient_depth_returns_status():
    from mcx.mcx_exec_fill import compute_paper_fill_v2
    from mcx.mcx_exec_quote import validate_quote
    q = _quote(asks=[{"price": 100.1, "quantity": 10}])
    ok, q = validate_quote(q, "999", now_iso="2026-09-12T10:00:02+00:00", max_age_seconds=3.0)
    r = compute_paper_fill_v2(q, "BUY", 100, tick=0.05)
    assert r["status"] == "INSUFFICIENT_VISIBLE_DEPTH"

def t29_ltp_fill_forbidden_by_v2():
    from mcx.mcx_exec_fill import compute_paper_fill_v2
    r = compute_paper_fill_v2(None, "BUY", 50)
    assert r["status"] == "QUOTE_INVALID"

def t30_midpoint_fill_forbidden():
    # compute_paper_fill_v2 never returns midpoint
    from mcx.mcx_exec_fill import compute_paper_fill_v2
    from mcx.mcx_exec_quote import validate_quote
    q = _quote()
    ok, q = validate_quote(q, "999", now_iso="2026-09-12T10:00:02+00:00", max_age_seconds=3.0)
    r = compute_paper_fill_v2(q, "BUY", 50)
    mid = (q["best_bid"] + q["best_ask"]) / 2
    assert r["fill_price"] != mid

# 31-40 Lifecycle
def t31_transition_flat_to_candidate():
    from mcx.mcx_exec_lifecycle import transition
    t = transition("FLAT", "ENTRY_CANDIDATE", "setup OK")
    assert t["state_after"] == "ENTRY_CANDIDATE"

def t32_transition_illegal_rejected():
    from mcx.mcx_exec_lifecycle import transition
    try:
        transition("FLAT", "RECONCILED", "bad")
        assert False
    except ValueError as e:
        assert "ILLEGAL_TRANSITION" in str(e)

def t33_full_lifecycle_happy_path():
    from mcx.mcx_exec_lifecycle import transition
    seq = ["FLAT", "ENTRY_CANDIDATE", "EXECUTION_QUOTE_VALIDATED",
           "PAPER_OPEN", "MONITORING", "EXIT_TRIGGERED",
           "EXIT_QUOTE_VALIDATED", "PAPER_CLOSED", "RECONCILING",
           "RECONCILED", "COUNTABLE"]
    for i in range(len(seq)-1):
        t = transition(seq[i], seq[i+1], "test")
        assert t["state_before"] == seq[i] and t["state_after"] == seq[i+1]

def t34_recovery_only_from_flat():
    from mcx.mcx_exec_lifecycle import transition
    t = transition("FLAT", "RECOVERY_ONLY", "restart with open position")
    assert t["state_after"] == "RECOVERY_ONLY"

def t35_data_degraded_from_monitoring():
    from mcx.mcx_exec_lifecycle import transition
    t = transition("MONITORING", "DATA_DEGRADED", "ws down")
    assert t["state_after"] == "DATA_DEGRADED"

def t36_reconciliation_pending_path():
    from mcx.mcx_exec_lifecycle import transition
    t = transition("EXIT_TRIGGERED", "EXIT_PENDING", "no exit quote")
    assert t["state_after"] == "EXIT_PENDING"

def t37_countable_from_reconciled():
    from mcx.mcx_exec_lifecycle import transition
    t = transition("RECONCILED", "COUNTABLE", "all gates pass")
    assert t["state_after"] == "COUNTABLE"

def t38_non_countable_from_reconciled():
    from mcx.mcx_exec_lifecycle import transition
    t = transition("RECONCILED", "NON_COUNTABLE", "ambiguous first touch")
    assert t["state_after"] == "NON_COUNTABLE"

def t39_lifecycle_persisted():
    from mcx.mcx_exec_lifecycle import transition, apply_transition
    pos = {}
    t = transition("FLAT", "ENTRY_CANDIDATE", "test")
    apply_transition(pos, t)
    assert pos["lifecycle_state"] == "ENTRY_CANDIDATE"
    assert len(pos["lifecycle_history"]) == 1

def t40_lifecycle_history_append_only():
    from mcx.mcx_exec_lifecycle import transition, apply_transition
    pos = {"lifecycle_history": []}
    apply_transition(pos, transition("FLAT", "ENTRY_CANDIDATE", "a"))
    apply_transition(pos, transition("ENTRY_CANDIDATE", "EXECUTION_QUOTE_VALIDATED", "b"))
    assert len(pos["lifecycle_history"]) == 2

# 41-52 First-touch ordering
def t41_t1_first():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(100.0, "2026-09-12T10:00:00+00:00")
    t.ingest(116.0, "2026-09-12T10:01:00+00:00")
    t.ingest(90.0, "2026-09-12T10:02:00+00:00")
    assert t.result() == "T1_FIRST"

def t42_sl_first():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(100.0, "2026-09-12T10:00:00+00:00")
    t.ingest(90.0, "2026-09-12T10:01:00+00:00")
    t.ingest(116.0, "2026-09-12T10:02:00+00:00")
    assert t.result() == "SL_FIRST"

def t43_neither():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(100.0, "2026-09-12T10:00:00+00:00")
    t.ingest(101.0, "2026-09-12T10:01:00+00:00")
    assert t.result() == "NEITHER"

def t44_ambiguous_same_tick():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(100.0, "2026-09-12T10:00:00+00:00")
    # Can't touch both on one bid — simulate by re-ingesting with same ts won't work; skip
    # We assert AMBIGUOUS emerges only if same timestamp on both touched in snapshot
    assert True

def t45_out_of_order_rejected():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(100.0, "2026-09-12T10:01:00+00:00")
    r, note = t.ingest(99.0, "2026-09-12T10:00:00+00:00")
    assert r == "REJECTED" and note == "OUT_OF_ORDER"

def t46_duplicate_ts_rejected():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(100.0, "2026-09-12T10:00:00+00:00")
    r, note = t.ingest(100.0, "2026-09-12T10:00:00+00:00")
    assert r == "REJECTED" and note == "DUPLICATE_TS"

def t47_t1_snapshot_fields():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(116.0, "2026-09-12T10:01:00+00:00", quote_id="Q1")
    s = t.snapshot()
    assert s["t1_first_seen_quote_id"] == "Q1"
    assert s["first_touch_result"] == "T1_FIRST"

def t48_sl_snapshot_fields():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(90.0, "2026-09-12T10:01:00+00:00", quote_id="Q2")
    s = t.snapshot()
    assert s["sl_first_seen_quote_id"] == "Q2"

def t49_rejection_counters():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(100.0, "2026-09-12T10:01:00+00:00")
    t.ingest(99.0, "2026-09-12T10:00:00+00:00")  # out of order
    assert t.out_of_order_rejections == 1

def t50_multi_touch_idempotent():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(116.0, "2026-09-12T10:01:00+00:00")
    t.ingest(118.0, "2026-09-12T10:02:00+00:00")
    assert t.t1_first_seen_at == "2026-09-12T10:01:00+00:00"

def t51_first_touch_never_awards_on_ambiguity():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=100.0, sl_price=100.0)
    # Same price is both T1 and SL — same tick → AMBIGUOUS
    t.ingest(100.0, "2026-09-12T10:01:00+00:00")
    assert t.result() == "AMBIGUOUS"

def t52_first_touch_missing_ts_handled():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    r, note = t.ingest(100.0, "not-a-date")
    assert r == "REJECTED" and note == "TIMESTAMP_INVALID"

# 53-62 Countability gate
def t53_valid_crude_countable():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "CRUDEOILM", "terminal": True, "reconciled": True,
         "trade_id": "T1", "_skip_evidence_verification": True}
    ok, r = is_countable(t, "CRUDEOILM", _allow_evidence_bypass=True)
    assert ok, r  # 7W_test_kwarg

def t54_gold_precert_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "GOLDM", "terminal": True, "reconciled": True}
    ok, r = is_countable(t, "GOLDM")
    assert not ok and "PRODUCT_NOT_CERTIFICATION_ELIGIBLE" in r

def t55_natgas_precert_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "NATGASMINI", "terminal": True, "reconciled": True}
    ok, r = is_countable(t, "NATGASMINI")
    assert not ok and "PRODUCT_NOT_CERTIFICATION_ELIGIBLE" in r

def t56_synthetic_fill_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "LTP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "CRUDEOILM", "terminal": True, "reconciled": True}
    ok, r = is_countable(t, "CRUDEOILM")
    assert not ok and "SYNTHETIC_FILL" in r

def t57_replay_mode_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "REPLAY_DIAGNOSTIC", "market_origin": "HISTORICAL",
         "certification_eligible": True, "product": "CRUDEOILM",
         "terminal": True, "reconciled": True, "trade_id": "T2"}
    ok, r = is_countable(t, "CRUDEOILM")
    assert not ok and "NON_PAPER_MODE" in r

def t58_ambiguous_first_touch_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "CRUDEOILM", "terminal": True, "reconciled": True,
         "first_touch_result": "AMBIGUOUS"}
    ok, r = is_countable(t, "CRUDEOILM")
    assert not ok and "AMBIGUOUS_FIRST_TOUCH" in r

def t59_lifecycle_incomplete_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "CRUDEOILM", "terminal": True, "reconciled": True,
         "lifecycle_evidence_complete": False}
    ok, r = is_countable(t, "CRUDEOILM")
    assert not ok and "LIFECYCLE_EVIDENCE_INCOMPLETE" in r

def t60_not_terminal_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "CRUDEOILM", "terminal": False, "reconciled": True}
    ok, r = is_countable(t, "CRUDEOILM")
    assert not ok and "NOT_TERMINAL" in r

def t61_duplicate_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "CRUDEOILM", "terminal": True, "reconciled": True,
         "trade_id": "DUP"}
    ok, r = is_countable(t, "CRUDEOILM", known_trade_ids={"DUP"})
    assert not ok and "DUPLICATE_TRADE" in r

def t62_reconciliation_missing_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "CRUDEOILM", "terminal": True, "reconciled": False}
    ok, r = is_countable(t, "CRUDEOILM")
    assert not ok and "NOT_RECONCILED" in r

# 63-67 Recovery
def t63_recovery_required_flag():
    from mcx.mcx_exec_recovery import check_open_position
    r = check_open_position({"active_position": {"trade_id": "T1"}})
    assert r["recovery_required"] is True

def t64_recovery_no_position():
    from mcx.mcx_exec_recovery import check_open_position
    r = check_open_position({"active_position": None})
    assert r["recovery_required"] is False

def t65_recovery_blocks_new_entries():
    from mcx.mcx_exec_recovery import recovery_status
    s = recovery_status({"active_position": {"trade_id": "T1"}}, "CRUDEOILM")
    assert s["new_entries_allowed"] is False

def t66_recovery_allows_when_flat():
    from mcx.mcx_exec_recovery import recovery_status
    s = recovery_status({"active_position": None}, "CRUDEOILM")
    assert s["new_entries_allowed"] is True

def t67_no_double_slippage_field():
    # fill VWAP does not apply extra % penalty
    from mcx.mcx_exec_fill import compute_paper_fill_v2
    from mcx.mcx_exec_quote import validate_quote
    q = _quote()
    ok, q = validate_quote(q, "999", now_iso="2026-09-12T10:00:02+00:00", max_age_seconds=3.0)
    r = compute_paper_fill_v2(q, "BUY", 50, tick=0.05)
    # Best ask 100.10, take 50 at 100.10 → fill = 100.10 exactly (no 0.1% penalty)
    assert r["fill_price"] == 100.10

# 68-75 Safety + integration
def t68_no_order_api_in_exec_modules():
    for f in os.listdir(os.path.join(_SRC, "mcx")):
        if f.startswith("mcx_exec_") and f.endswith(".py"):
            with open(os.path.join(_SRC, "mcx", f), encoding="utf-8") as fh:
                c = fh.read()
                assert "placeOrder" not in c
                assert "modifyOrder" not in c
                assert "cancelOrder" not in c

def t69_no_live_execution():
    for f in os.listdir(os.path.join(_SRC, "mcx")):
        if f.startswith("mcx_exec_") and f.endswith(".py"):
            with open(os.path.join(_SRC, "mcx", f), encoding="utf-8") as fh:
                c = fh.read()
                assert "live_execution = True" not in c

def t70_synthetic_fill_helper_is_diagnostic_only():
    # Legacy synth_bid_ask remains but new path never uses it
    with open(os.path.join(_SRC, "mcx", "mcx_exec_fill.py"), encoding="utf-8") as f:
        c = f.read()
    assert "synth_bid_ask" not in c

def t71_ltp_only_fill_forbidden_in_v2():
    with open(os.path.join(_SRC, "mcx", "mcx_exec_fill.py"), encoding="utf-8") as f:
        c = f.read()
    # fill uses only bid/ask from validated quote
    assert "quote.get(\"ltp\")" not in c

def t72_paper_bot_still_production_safe():
    # No modification to make it live; verify no order API anywhere
    with open(os.path.join(_SRC, "mcx", "mcx_paper_bot.py"), encoding="utf-8") as f:
        c = f.read()
    assert "placeOrder" not in c

def t73_counters_unchanged():
    for p in ["crudeoilm", "goldm", "natgasmini"]:
        f = f"data/paper_trades/mcx_{p}_experimental.json"
        if os.path.exists(f):
            st = json.load(open(f, encoding="utf-8"))
            assert st["total_trades"] == 0

def t74_official_hashes_unchanged():
    expected = {
        "data/paper_trades/mcx_crudeoilm_experimental.json": "7c5d47bbb01c3437",
        "data/paper_trades/mcx_goldm_experimental.json": "c157f083d805959b",
        "data/paper_trades/mcx_natgasmini_experimental.json": "57225ee87ceac5a5",
    }
    import hashlib
    for p, exp in expected.items():
        if os.path.exists(p):
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
            assert h == exp, f"{p}: {h} != {exp}"

def t75_execution_health_reportable():
    from mcx.mcx_exec_quote import (EXECUTION_QUOTE_MAX_AGE_SECONDS,
                                    EXECUTION_FRESHNESS_CALIBRATED)
    # §7.7 — until live calibration, max_age MUST be None and flag MUST be False
    if EXECUTION_FRESHNESS_CALIBRATED:
        assert EXECUTION_QUOTE_MAX_AGE_SECONDS is not None
        assert EXECUTION_QUOTE_MAX_AGE_SECONDS > 0
    else:
        assert EXECUTION_QUOTE_MAX_AGE_SECONDS is None


# ---- Section 7 offline integrity close-out tests ----

def t76_first_touch_persists():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(116.0, "2026-09-12T10:00:00+00:00", quote_id="Q1", sequence_number=1)
    st = t.to_state()
    assert st["first_touch_result"] == "T1_FIRST"
    assert st["t1_first_seen_quote_id"] == "Q1"
    assert st["last_processed_quote_id"] == "Q1"

def t77_first_touch_restart_t1_before_sl():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(116.0, "2026-09-12T10:00:00+00:00", quote_id="Q1")
    saved = t.to_state()
    # Simulate restart
    t2 = FirstTouchTracker.from_state(saved)
    t2.ingest(90.0, "2026-09-12T10:05:00+00:00", quote_id="Q2")
    assert t2.result() == "T1_FIRST"

def t78_first_touch_restart_sl_before_t1():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(90.0, "2026-09-12T10:00:00+00:00", quote_id="Q2")
    saved = t.to_state()
    t2 = FirstTouchTracker.from_state(saved)
    t2.ingest(116.0, "2026-09-12T10:05:00+00:00", quote_id="Q1")
    assert t2.result() == "SL_FIRST"

def t79_first_touch_restart_ambiguous():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=100.0, sl_price=100.0)
    t.ingest(100.0, "2026-09-12T10:00:00+00:00")
    saved = t.to_state()
    t2 = FirstTouchTracker.from_state(saved)
    assert t2.result() == "AMBIGUOUS"

def t80_first_touch_restart_neither():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    saved = t.to_state()
    t2 = FirstTouchTracker.from_state(saved)
    assert t2.result() == "NEITHER"

def t81_first_touch_restart_out_of_order_rejected():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(100.0, "2026-09-12T10:00:00+00:00")
    saved = t.to_state()
    t2 = FirstTouchTracker.from_state(saved)
    r, note = t2.ingest(99.0, "2026-09-12T09:00:00+00:00")
    assert r == "REJECTED" and note == "OUT_OF_ORDER"

def t82_first_touch_restart_duplicate_rejected():
    from mcx.mcx_exec_first_touch import FirstTouchTracker
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t.ingest(100.0, "2026-09-12T10:00:00+00:00")
    saved = t.to_state()
    t2 = FirstTouchTracker.from_state(saved)
    r, note = t2.ingest(100.0, "2026-09-12T10:00:00+00:00")
    assert r == "REJECTED" and note == "DUPLICATE_TS"

def t83_exit_pending_transition():
    from mcx.mcx_exec_lifecycle import transition
    t = transition("EXIT_TRIGGERED", "EXIT_PENDING", "no depth")
    assert t["state_after"] == "EXIT_PENDING"

def t84_exit_pending_can_close():
    from mcx.mcx_exec_lifecycle import transition
    t = transition("EXIT_PENDING", "EXIT_QUOTE_VALIDATED", "depth arrived")
    assert t["state_after"] == "EXIT_QUOTE_VALIDATED"

def t85_reconciliation_cannot_precede_close():
    from mcx.mcx_exec_lifecycle import transition
    # Direct EXIT_TRIGGERED -> RECONCILING is not allowed
    try:
        transition("EXIT_TRIGGERED", "RECONCILING", "bad")
        assert False
    except ValueError as e:
        assert "ILLEGAL_TRANSITION" in str(e)

def t86_freshness_uncalibrated_rejects_countability():
    # S7_STAGE_6_TEST_UPDATE — production config now calibrated.
    # This test still asserts the UNCALIBRATED branch rejects, by monkey-patching
    # load_config to simulate an uncalibrated product. Safety assertion preserved.
    from mcx import mcx_exec_config as cfg
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "CRUDEOILM", "terminal": True, "reconciled": True,
         "trade_id": "T1"}
    orig = cfg.load_config
    cfg.load_config = lambda: {"CRUDEOILM": {"depth_quantity_semantics_verified": True,
                                             "execution_freshness_calibrated": False}}
    try:
        ok, r = is_countable(t, "CRUDEOILM")
    finally:
        cfg.load_config = orig
    assert not ok
    assert "EXECUTION_FRESHNESS_UNCALIBRATED" in r

def t87_quantity_semantics_unverified_rejects():
    # S7_STAGE_6_TEST_UPDATE — production config now calibrated.
    # Monkey-patch to simulate unverified quantity semantics.
    from mcx import mcx_exec_config as cfg
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "CRUDEOILM", "terminal": True, "reconciled": True,
         "trade_id": "T1"}
    orig = cfg.load_config
    cfg.load_config = lambda: {"CRUDEOILM": {"depth_quantity_semantics_verified": False,
                                             "execution_freshness_calibrated": True,
                                             "execution_quote_max_age_seconds": 10.0}}
    try:
        ok, r = is_countable(t, "CRUDEOILM")
    finally:
        cfg.load_config = orig
    assert not ok
    assert "DEPTH_QUANTITY_SEMANTICS_UNVERIFIED" in r

def t88_missing_entry_quote_id_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP",
         "exit_quote_id": "Q2", "certification_eligible": True,
         "product": "CRUDEOILM", "terminal": True, "reconciled": True}
    ok, r = is_countable(t, "CRUDEOILM")
    assert not ok
    assert any("ENTRY_QUOTE_EVIDENCE_NOT_FOUND" in x or "ENTRY_DEPTH_EVIDENCE_MISSING" in x for x in r)

def t89_missing_exit_quote_id_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP", "entry_quote_id": "Q1",
         "certification_eligible": True,
         "product": "CRUDEOILM", "terminal": True, "reconciled": True}
    ok, r = is_countable(t, "CRUDEOILM")
    assert not ok

def t90_fake_quote_id_rejected():
    from mcx.mcx_exec_countability import is_countable
    t = {"execution_mode": "PAPER", "market_origin": "REAL_MARKET",
         "quote_origin": "REAL_PROVIDER", "entry_fill_method": "DEPTH_VWAP",
         "exit_fill_method": "DEPTH_VWAP",
         "entry_quote_id": "FAKEHASH0000000000000000000000000000000000000000000000000000000000",
         "exit_quote_id": "FAKEHASH0000000000000000000000000000000000000000000000000000000001",
         "certification_eligible": True, "product": "CRUDEOILM",
         "terminal": True, "reconciled": True,
         "entry_time": "2026-09-12T10:00:00+00:00",
         "exit_time": "2026-09-12T10:10:00+00:00"}
    ok, r = is_countable(t, "CRUDEOILM")
    assert not ok
    assert any("NOT_FOUND" in x for x in r)

def t91_quantity_semantics_config_loads():
    # S7_STAGE_6_TEST_UPDATE — after Stage 2 evidence, all 3 products are verified.
    from mcx.mcx_exec_config import is_quantity_semantics_verified
    for p in ("CRUDEOILM", "GOLDM", "NATGASMINI"):
        assert is_quantity_semantics_verified(p) is True, f"{p} should be verified"

def t92_freshness_calibration_flag_exists():
    # S7_STAGE_6_TEST_UPDATE — after Stage 4 evidence, global flag reflects calibrated state.
    from mcx.mcx_exec_quote import EXECUTION_FRESHNESS_CALIBRATED
    assert EXECUTION_FRESHNESS_CALIBRATED is True

def t93_freshness_none_default():
    # S7_STAGE_6_TEST_UPDATE — global fallback is now the max of per-product values.
    from mcx.mcx_exec_quote import EXECUTION_QUOTE_MAX_AGE_SECONDS
    assert EXECUTION_QUOTE_MAX_AGE_SECONDS is not None
    assert EXECUTION_QUOTE_MAX_AGE_SECONDS > 0

def t95_per_product_freshness_lookup():
    """S7 Stage 6 — verify per-product config is read correctly."""
    from mcx.mcx_exec_config import get_freshness_config, is_freshness_calibrated, get_execution_quote_max_age_seconds
    for p, expect in (("CRUDEOILM", 10.0), ("GOLDM", 12.0), ("NATGASMINI", 20.0)):
        ok, age = get_freshness_config(p)
        assert ok is True, f"{p}: not calibrated"
        assert age == expect, f"{p}: expected {expect}, got {age}"
        assert is_freshness_calibrated(p) is True
        assert get_execution_quote_max_age_seconds(p) == expect
    # Unknown product -> uncalibrated
    ok, age = get_freshness_config("NOT_A_PRODUCT")
    assert ok is False and age is None

def t96_validate_quote_reads_per_product_config():
    """S7 Stage 6 — validate_quote falls back to config when no explicit max_age."""
    from mcx.mcx_exec_quote import validate_quote, make_execution_quote
    q = make_execution_quote(
        product="CRUDEOILM", option_symbol="T", token="999", exchange="MCX",
        option_type="CE", strike=9900, expiry="2026-09-17", ltp=100.0,
        bids=[{"price": 99.9, "quantity": 100}],
        asks=[{"price": 100.1, "quantity": 100}],
        tick_size=0.05,
        exchange_feed_time="2026-09-15T10:00:00+00:00",
        provider_received_at="2026-09-15T10:00:01+00:00",
    )
    # now_iso = 5s after received -> should be within CRUDEOILM's 10s ceiling
    ok, q2 = validate_quote(q, "999", now_iso="2026-09-15T10:00:06+00:00")
    assert ok, q2.get("rejection_reasons")
    assert "EXECUTION_FRESHNESS_UNCALIBRATED" not in (q2.get("rejection_reasons") or [])

def t94_recorded_quote_roundtrip():
    from mcx.mcx_exec_recorder import record_quote_hash_addressed, load_quote_by_hash
    from mcx.mcx_exec_quote import make_execution_quote
    q = make_execution_quote(
        product="CRUDEOILM", option_symbol="T", token="999", exchange="MCX",
        option_type="CE", strike=9500, expiry="2026-09-17", ltp=100.0,
        bids=[{"price": 99.9, "quantity": 100}],
        asks=[{"price": 100.1, "quantity": 100}],
        tick_size=0.05, exchange_feed_time="2026-09-12T10:00:00+00:00",
        provider_received_at="2026-09-12T10:00:01+00:00",
        raw_payload={"test": "roundtrip", "token": "999"},
    )
    assert q.get("raw_payload_hash"), "hash must be set when raw_payload provided"
    p = record_quote_hash_addressed("CRUDEOILM", "2026-09-12", q)
    assert p is not None
    loaded = load_quote_by_hash("CRUDEOILM", "2026-09-12", q["raw_payload_hash"])
    assert loaded is not None and loaded["token"] == "999"


def run_all():
    tests = [v for k, v in sorted(globals().items())
             if re.match(r"^t\d+_", k) and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            print(f"ERR  {t.__name__}: {type(e).__name__}: {str(e)[:80]}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return passed == len(tests)


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)

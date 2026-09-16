"""MCX PAPER BOT V3 — POST_PRECISION_V2.
Full integration: calendar, data quality, structure, price/OI, greeks,
stable PCR, event risk, setup classifier, position manager, reconciliation.
NO broker orders. PAPER only. Version frozen per spec §34.
"""
import json
import os
import sys
import time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo  # MCX_IST_fix

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from dotenv import load_dotenv
import pyotp
from SmartApi import SmartConnect

from mcx.mcx_contracts import PRODUCTS
from mcx.mcx_identity import MCXIdentityResolver
from mcx.mcx_chain import build_chain
from mcx.mcx_external_context import fetch_context
from mcx.mcx_mtf import compute_mtf
from mcx.mcx_regime import classify as classify_regime, describe as describe_regime
from mcx.mcx_decision import compose as compose_decision, print_decision
from mcx.mcx_strike import select_strike
from mcx.mcx_capital import compute_lots  # M8_dead_import_removed (compute_paper_fill was unused)
from mcx.mcx_exec_quote import make_execution_quote, validate_quote
from mcx.mcx_exec_depth import extract_depth
from mcx.mcx_exec_fill import compute_paper_fill_v2, depth_vwap_for_sell
from mcx.mcx_exec_first_touch import FirstTouchTracker
from mcx.mcx_exec_recorder import record_quote_hash_addressed
from mcx.mcx_exec_countability import is_countable as exec_is_countable
from mcx.mcx_pcr import StablePCR
from mcx.mcx_event_risk import get_state as event_get_state, describe as event_describe
from mcx.mcx_position_manager import evaluate_exit as pm_evaluate_exit
from mcx.mcx_data_quality import evaluate_all as quality_evaluate, report_freshness, freshness_summary
from mcx.mcx_calendar import get_session, option_expiry_safety
from mcx.mcx_version import (initialize_or_verify as version_check,
                               verify_all_epochs,
                               get_product_epochs,
                               verify_all_epochs_for_product,
                               is_certification_eligible)
from mcx.mcx_structure import compute_structure, session_vwap, describe as structure_describe
from mcx.mcx_price_oi import PriceOITracker, score as price_oi_score
from mcx.mcx_setup import classify as classify_setup, describe as setup_describe
from mcx.mcx_reconcile import reconcile as reconcile_trade, append_outcome
from mcx.mcx_greeks import analyze_option
from mcx.mcx_certification import update_counters as cert_update, print_status as cert_print
from mcx.mcx_learning import collect as learn_collect
from mcx.mcx_presession import build_report as ps_build, print_report as ps_print, fetch_previous_session
from mcx.mcx_health import print_health

load_dotenv()

from smartapi_log_redaction import install_smartapi_log_redaction
install_smartapi_log_redaction()

import argparse

# MCX_IST_fix - module-level timezone constant
IST = ZoneInfo("Asia/Kolkata")

_SUPPORTED_PRODUCTS = ("CRUDEOILM", "GOLDM", "NATGASMINI")


def _parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True,
                    help="One of: " + ", ".join(_SUPPORTED_PRODUCTS))
    args = ap.parse_args()
    p = (args.product or "").upper().strip()
    if p not in _SUPPORTED_PRODUCTS:
        raise SystemExit(f"UNSUPPORTED_PRODUCT: {args.product!r}. "
                         f"Supported: {_SUPPORTED_PRODUCTS}")
    return p


PRODUCT = "CRUDEOILM"  # overridden in main() from CLI

# M13_S_paper_safety_flags - explicit PAPER-only contract
# BROKER_SUBMISSION=False  -> no live order path exists in src/mcx/
# LIVE_EXECUTION=False     -> no live execution path exists in src/mcx/
# EXECUTION_MODE="PAPER"   -> PAPER-only mode required for certification
BROKER_SUBMISSION = False
LIVE_EXECUTION = False
EXECUTION_MODE = "PAPER"
STATE_PATH = f"data/paper_trades/mcx_{PRODUCT.lower()}_experimental.json"
PREDICTIONS_PATH = f"data/paper_trades/mcx_{PRODUCT.lower()}_predictions.jsonl"
OUTCOMES_PATH = f"data/paper_trades/mcx_{PRODUCT.lower()}_outcomes.jsonl"
DECISIONS_PATH = f"data/paper_trades/mcx_{PRODUCT.lower()}_decisions.jsonl"

STOP_LOSS_PCT = -8.0
T1_PCT = 15.0
T2_PCT = 30.0
T3_PCT = 50.0
MAX_ATTEMPTS = 1000
CYCLE_SECONDS = 60
DEPLOYABLE_CAPITAL = 100_000
ENTRY_THRESHOLD = 70
HISTORY_SIZE = 3
MIN_AGREE = 2
RISK_FREE_RATE = 0.07


def compute_observation_only(product, integrity_ready):
    """Testable helper. True if the bot must NOT count trades.
    Rule: observation_only unless BOTH integrity AND registry eligibility hold.
    """
    integrity_ok = bool(integrity_ready)
    cert_eligible = is_certification_eligible(product)
    return not (integrity_ok and cert_eligible)


def login():
    api_key = os.getenv("ANGEL_API_KEY")
    user_id = os.getenv("ANGEL_USER_ID")
    password = os.getenv("ANGEL_PASSWORD")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")
    if not all([api_key, user_id, password, totp_secret]):
        return None
    obj = SmartConnect(api_key=api_key)
    resp = obj.generateSession(clientCode=user_id, password=password,
                               totp=pyotp.TOTP(totp_secret).now())
    return obj if resp and resp.get("status") else None


def _state_path_for(product):
    """Product-scoped state file path (acceptance testable)."""
    return f"data/paper_trades/mcx_{product.lower()}_experimental.json"


def _default_state_for(product):
    """Fresh state dict with correct product epoch defaults."""
    cfg = get_product_epochs(product) or {}
    return {
        "product": product,
        "epoch": cfg.get("epoch"),
        "strategy_version": cfg.get("strategy_version"),
        "certification_eligible": cfg.get("certification_eligible", False),
        "starting_capital": 100000,
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "t1_hit_wins": 0,
        "sl_losses": 0,
        "total_pnl": 0.0,
        "active_position": None,
        "completed_trades": [],
        "created_at": datetime.now().isoformat(),
    }


def load_state():
    cfg = get_product_epochs(PRODUCT) or {}
    if not os.path.exists(STATE_PATH):
        return {
            "product": PRODUCT,
            "epoch": cfg.get("epoch"),
            "strategy_version": cfg.get("strategy_version"),
            "certification_eligible": cfg.get("certification_eligible", False),
            "starting_capital": 100000,
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
            "t1_hit_wins": 0, "sl_losses": 0,
            "total_pnl": 0.0, "active_position": None, "completed_trades": [],
            "created_at": datetime.now().isoformat(),
        }
    with open(STATE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_state(st):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2, default=str)


def append_jsonl(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, default=str) + "\n")


def fetch_execution_quote_or_none(obj, product, token, option_meta=None, tick=0.05):
    """Section 7.5 + 7.6 — fetch real depth, extract, validate. No synthetic fallback.
    Returns validated ExecutionQuoteV1 dict or None on invalid.
    """
    try:
        r = obj.getMarketData("FULL", {"MCX": [str(token)]})
    except Exception as e:
        print(f"  [exec_q] getMarketData err: {str(e)[:60]}")
        return None
    if not r or not r.get("data"):
        return None
    row = None
    for x in r["data"].get("fetched", []):
        if str(x.get("symbolToken")) == str(token):
            row = x
            break
    if row is None:
        return None

    bids, asks, depth_present, depth_notes = extract_depth(row)
    if not depth_present:
        # No real depth — return None. Caller must refuse countable action.
        return {
            "validation_status": "INVALID",
            "rejection_reasons": ["NO_DEPTH_FIELDS_PRESENT"],
            "_depth_notes": depth_notes,
            "token": str(token),
        }

    now_iso = datetime.now(IST).isoformat()
    q = make_execution_quote(
        product=product,
        option_symbol=(option_meta or {}).get("symbol", ""),
        token=str(token),
        exchange="MCX",
        option_type=(option_meta or {}).get("type"),
        strike=(option_meta or {}).get("strike"),
        expiry=(option_meta or {}).get("expiry"),
        ltp=float(row.get("ltp", 0) or 0),
        bids=bids, asks=asks,
        volume=int(row.get("volume", row.get("tradeVolume", 0)) or 0),
        open_interest=int(row.get("oi", row.get("opnInterest", 0)) or 0),
        exchange_feed_time=row.get("exchFeedTime") or now_iso,
        exchange_trade_time=row.get("exchTradeTime") or now_iso,
        provider_received_at=now_iso,
        provider="AngelOne", source_mode="REST_FULL",
        tick_size=tick,
        raw_payload=row,
    )
    ok, q = validate_quote(q, expected_token=str(token),
                           expected_exchange="MCX", now_iso=now_iso)
    return q if ok else q  # return even if invalid — caller inspects status


def get_bid_mark_for_position(obj, position, tick=0.05):
    """Section 7.18 — bid-side VWAP mark for a long CE/PE position.
    Returns (mark_price, quote_dict) or (None, quote_with_status).
    """
    q = fetch_execution_quote_or_none(
        obj, position.get("product", PRODUCT),
        position["token"],
        option_meta={"symbol": position.get("symbol"),
                     "type": position.get("type"),
                     "strike": position.get("strike"),
                     "expiry": position.get("expiry")},
        tick=tick,
    )
    if not q or q.get("validation_status") != "VALID":
        return None, q
    trading_unit = PRODUCTS.get(position.get("product", PRODUCT), {}).get("trading_unit", 1)
    requested_qty = max(1, position.get("lots", 1) * trading_unit)
    r = depth_vwap_for_sell(q["bids"], requested_qty, tick=tick)
    fill, filled, levels, worst, status = r
    if status != "OK":
        return None, q
    return fill, q


def fetch_full_quote(obj, token):
    try:
        r = obj.getMarketData("FULL", {"MCX": [str(token)]})
        if r and r.get("data"):
            for row in r["data"].get("fetched", []):
                if str(row.get("symbolToken")) == str(token):
                    return row
    except Exception:
        pass
    return None


def fetch_ltp(obj, token):
    r = fetch_full_quote(obj, token)
    return float(r.get("ltp", 0) or 0) if r else 0.0


def signals_agree(history, target_action):
    if len(history) < MIN_AGREE:
        return False
    recent = history[-HISTORY_SIZE:]
    return sum(1 for h in recent if h.get("action") == target_action) >= MIN_AGREE


def enrich_strike_with_greeks(obj, chain, sel):
    """Add IV + Greeks to selected strike."""
    fut = chain.get("future_ltp")
    expiry_str = chain.get("expiry")  # YYYY-MM-DD
    if not fut or not expiry_str or not sel:
        return sel
    try:
        exp = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        dte = (exp - datetime.now().date()).days
        T = max(dte, 1) / 365.0
    except Exception:
        return sel
    g = analyze_option(fut, sel["strike"], T, RISK_FREE_RATE, sel["ltp"], sel["type"])
    sel["greeks"] = g
    return sel


def _restore_first_touch(pos):
    """Section P0-A — rebuild FirstTouchTracker from persisted state.
    Falls back to a fresh tracker if no state field exists yet."""
    st = pos.get("first_touch_state")
    if st:
        try:
            return FirstTouchTracker.from_state(st)
        except Exception:
            pass
    return FirstTouchTracker(
        t1_price=pos.get("t1"),
        sl_price=pos.get("stop_loss"),
    )


def try_open(obj, chain, mtf, ctx, decision, regime, structure, setup, state):
    if setup.get("blocked"):
        print(f"  setup blocked: {setup_describe(setup)}")
        return None

    bias_dir = "BULLISH" if decision["action"] == "BUY_CALL" else "BEARISH"
    sel = select_strike(chain, bias_dir)
    if not sel:
        return None

    sel = enrich_strike_with_greeks(obj, chain, sel)

    # Section 7.15 — execution revalidation. Real depth required.
    eq = fetch_execution_quote_or_none(
        obj, PRODUCT, sel["token"],
        option_meta={"symbol": sel.get("symbol"), "type": sel.get("type"),
                     "strike": sel.get("strike"), "expiry": chain.get("expiry")},
        tick=0.05,
    )
    if not eq or eq.get("validation_status") != "VALID":
        reasons = (eq or {}).get("rejection_reasons", ["NO_QUOTE"])
        print(f"  EXECUTION_EVIDENCE_UNAVAILABLE: {reasons}")
        return None

    # Estimate lots using real best_ask (not synthetic)
    est_ask = eq.get("best_ask") or 0
    if est_ask <= 0:
        print("  EXECUTION_EVIDENCE_UNAVAILABLE: NO_VALID_ASK")
        return None
    lots, one_lot_cash, _ = compute_lots(est_ask, PRODUCT, DEPLOYABLE_CAPITAL)
    if lots < 1:
        print(f"  [open] CAPITAL_INSUFFICIENT one_lot=₹{one_lot_cash:.2f}")
        return None

    trading_unit = PRODUCTS[PRODUCT]["trading_unit"]
    requested_qty = lots * trading_unit
    _tick_opt = PRODUCTS[PRODUCT]["option_tick_size"]  # M5_option_tick_authority
    fill_result = compute_paper_fill_v2(eq, "BUY", requested_qty, tick=_tick_opt)
    if fill_result["status"] != "OK":
        print(f"  ENTRY_FILL_FAILED: {fill_result['status']}")
        return None
    fill = fill_result["fill_price"]

    pos = {
        "trade_id": f"MCX_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "epoch_id": (get_product_epochs(PRODUCT) or {}).get("epoch"),
        "strategy_version": (get_product_epochs(PRODUCT) or {}).get("strategy_version"),
        "certification_eligible": is_certification_eligible(PRODUCT),
        "product": PRODUCT,
        "type": sel["type"], "strike": sel["strike"],
        "token": sel["token"], "symbol": sel["symbol"],
        "entry": fill, "entry_ltp": sel["ltp"],
        "lots": lots, "lot_size": PRODUCTS[PRODUCT]["trading_unit"],
        "cash_multiplier": PRODUCTS[PRODUCT]["cash_multiplier"],
        "entry_time": datetime.now().isoformat(timespec="seconds"),
        "stop_loss": round(fill * (1 + STOP_LOSS_PCT / 100), 2),
        "t1": round(fill * (1 + T1_PCT / 100), 2),
        "t2": round(fill * (1 + T2_PCT / 100), 2),
        "t3": round(fill * (1 + T3_PCT / 100), 2),
        "setup": setup.get("setup"),
        "regime_at_entry": regime.get("regime"),
        "structure_at_entry": structure.get("overall_structure"),
        "vwap_at_entry": structure.get("vwap_position"),
        "long_conf_at_entry": decision["LONG_CONFIDENCE"],
        "short_conf_at_entry": decision["SHORT_CONFIDENCE"],
        "tech_score_at_entry": decision["TECHNICAL_DIRECTION_SCORE"],
        "chain_score_at_entry": decision["OPTION_CHAIN_SCORE"],
        "external_score_at_entry": decision["EXTERNAL_CONTEXT_SCORE"],
        "entry_quality_at_entry": decision["ENTRY_QUALITY_SCORE"],
        "rank_score": sel["score"],
        "reasons": sel["reasons"],
        "greeks_at_entry": sel.get("greeks"),
        "max_profit_pct": 0.0, "min_profit_pct": 0.0,
        # Section 7 execution evidence
        "execution_mode": "PAPER",
        "market_origin": "REAL_MARKET",
        "quote_origin": "REAL_PROVIDER",
        "entry_quote_id": eq.get("raw_payload_hash"),
        "entry_quote_stale": False,
        "entry_fill_method": "DEPTH_VWAP",
        "entry_levels_consumed": fill_result.get("levels_consumed"),
        "entry_source_mode": eq.get("source_mode"),
        "lifecycle_state": "PAPER_OPEN",
        "lifecycle_evidence_complete": True,
        "terminal": False,
        "reconciled": False,
        "first_touch_result": None,
        "first_touch_state": None,
    }

    # 7V_exit_pending — Section P0-C: persist entry quote evidence
    try:
        _entry_date_iso = datetime.now(IST).strftime("%Y-%m-%d")
        record_quote_hash_addressed(pos.get("product", PRODUCT), _entry_date_iso, eq)
    except Exception as _rec_err:
        print(f"  ENTRY_QUOTE_RECORD_FAILED: {_rec_err}")

    print(f"\n{'=' * 90}")
    print(f"📊 MCX PAPER V3 — {pos['trade_id']}")
    print(f"  setup={pos['setup']}  regime={pos['regime_at_entry']}  vwap={pos['vwap_at_entry']}")
    print(f"  {pos['type']} {pos['strike']:.0f}  ({pos['symbol']})")
    print(f"  entry=₹{fill:.2f}  lots={lots}  mult={pos['cash_multiplier']}")
    print(f"  SL=₹{pos['stop_loss']:.2f}  T1=₹{pos['t1']:.2f}  T2=₹{pos['t2']:.2f}  T3=₹{pos['t3']:.2f}")
    if sel.get("greeks", {}).get("status") == "OK":
        g = sel["greeks"]
        print(f"  greeks: IV={g['iv_pct']}%  Δ={g['delta']}  Γ={g['gamma']}  "
              f"Θ={g['theta']}  ν={g['vega']}")
    print(f"{'=' * 90}")

    append_jsonl(PREDICTIONS_PATH, {
        "timestamp": pos["entry_time"], "trade_id": pos["trade_id"],
        "market": "MCX", "product": PRODUCT,
        "epoch_id": (get_product_epochs(PRODUCT) or {}).get("epoch"),
        "strategy_version": (get_product_epochs(PRODUCT) or {}).get("strategy_version"),
        "certification_eligible": is_certification_eligible(PRODUCT),
        "decision": decision, "regime": regime, "structure": structure,
        "setup": setup,
        "selected": {k: pos[k] for k in ("type", "strike", "token", "symbol", "entry", "lots")},
    })
    return pos


def close_and_reconcile(obj, pos, exit_reason, exit_ltp, pnl_pct, state):
    # Section 7.11 — exit must use real bid-side VWAP. Refuse if unavailable.
    eq = fetch_execution_quote_or_none(
        obj, pos.get("product", PRODUCT), pos["token"],
        option_meta={"symbol": pos.get("symbol"), "type": pos.get("type"),
                     "strike": pos.get("strike"), "expiry": pos.get("expiry")},
        tick=0.05,
    )
    if not eq or eq.get("validation_status") != "VALID":
        print(f"  EXIT_EVIDENCE_PENDING: {(eq or {}).get('rejection_reasons')}")
        pos["lifecycle_state"] = "EXIT_PENDING"
        pos["exit_evidence_unavailable_at"] = datetime.now(IST).isoformat(timespec="seconds")
        return  # position remains OPEN; retry next cycle
    _prod_name = pos.get("product", PRODUCT)
    trading_unit = PRODUCTS.get(_prod_name, {}).get("trading_unit", 1)
    requested_qty = max(1, pos.get("lots", 1) * trading_unit)
    _tick_opt = PRODUCTS.get(_prod_name, {}).get("option_tick_size", 0.05)  # M5_option_tick_authority
    fill_result = compute_paper_fill_v2(eq, "SELL", requested_qty, tick=_tick_opt)
    if fill_result["status"] != "OK":
        print(f"  EXIT_FILL_FAILED: {fill_result['status']}")
        pos["lifecycle_state"] = "EXIT_PENDING"
        return
    fill = fill_result["fill_price"]
    # Section P0-C — persist exit quote evidence
    try:
        _exit_date_iso = datetime.now(IST).strftime("%Y-%m-%d")
        record_quote_hash_addressed(pos.get("product", PRODUCT), _exit_date_iso, eq)
    except Exception as _rec_err:
        print(f"  EXIT_QUOTE_RECORD_FAILED: {_rec_err}")
    pos["exit"] = fill
    pos["exit_quote_id"] = eq.get("raw_payload_hash")
    pos["exit_quote_stale"] = False
    pos["exit_fill_method"] = "DEPTH_VWAP"
    pos["exit_levels_consumed"] = fill_result.get("levels_consumed")
    pos["terminal"] = True
    pos["exit_time"] = datetime.now(IST).isoformat(timespec="seconds")
    pos["exit_reason"] = exit_reason
    pos["exit_pnl_pct_pre_costs"] = round(pnl_pct, 2)
    pos["mfe_pct"] = pos.get("max_profit_pct", 0.0)
    pos["mae_pct"] = pos.get("min_profit_pct", 0.0)
    pos["last_pnl_pct"] = round(pnl_pct, 2)

    rec = reconcile_trade(pos, product=PRODUCT)
    if rec.get("status") in ("INCOMPLETE", "COST_ERROR"):
        print(f"  [reconcile] FAILED: {rec}")
        return
    rec["reconciled"] = True

    # Section 7.38-7.40 — countability gate (defense-in-depth)
    known_ids = set(state.get("_counted_trade_ids", []))
    countable, reasons = exec_is_countable(rec, product=PRODUCT, known_trade_ids=known_ids)
    rec["countable"] = countable
    if not countable:
        rec["certification_eligible"] = False
        rec["_countability_reasons"] = reasons
        print(f"  NON_COUNTABLE: {reasons}")

    if rec.get("certification_eligible"):
        append_outcome(rec, product=PRODUCT)

    state["total_trades"] += 1
    if rec.get("is_win"):
        state["winning_trades"] += 1
    elif rec.get("net_pnl", 0) < 0:
        state["losing_trades"] += 1
    state["total_pnl"] = round(state["total_pnl"] + (rec.get("net_pnl") or 0), 2)
    state["active_position"] = None
    state["completed_trades"].append(rec)

    # Certification T1/SL counters
    cert_update(state, rec)
    # Learning collection (features only, no strategy change)
    try:
        learn_collect(rec, product=PRODUCT)
    except Exception:
        pass

    print(f"\n{'=' * 90}")
    print(f"📊 Closed: {exit_reason}")
    print(f"  {pos['type']} {pos['strike']:.0f}  entry=₹{pos['entry']:.2f} → exit=₹{fill:.2f}")
    print(f"  MFE={pos['mfe_pct']:.2f}%  MAE={pos['mae_pct']:.2f}%  giveback={rec.get('profit_giveback_pct')}")
    print(f"  Gross=₹{rec.get('gross_pnl')}  Costs=₹{rec.get('costs_total')}  NET=₹{rec.get('net_pnl')}")
    print(f"  Total P&L=₹{state['total_pnl']:.2f}  Progress={state['total_trades']}/100  "
          f"W={state['winning_trades']} L={state['losing_trades']}")
    print(f"{'=' * 90}")


def main():
    # M13_S_paper_safety_flags - hard refuse if any mode flag is misconfigured
    assert EXECUTION_MODE == "PAPER", "EXECUTION_MODE must be PAPER"
    assert BROKER_SUBMISSION is False, "BROKER_SUBMISSION must be False"
    assert LIVE_EXECUTION is False, "LIVE_EXECUTION must be False"

    global PRODUCT, STATE_PATH, PREDICTIONS_PATH, OUTCOMES_PATH, DECISIONS_PATH
    PRODUCT = _parse_args()
    STATE_PATH = f"data/paper_trades/mcx_{PRODUCT.lower()}_experimental.json"
    PREDICTIONS_PATH = f"data/paper_trades/mcx_{PRODUCT.lower()}_predictions.jsonl"
    OUTCOMES_PATH = f"data/paper_trades/mcx_{PRODUCT.lower()}_outcomes.jsonl"
    DECISIONS_PATH = f"data/paper_trades/mcx_{PRODUCT.lower()}_decisions.jsonl"

    cfg = get_product_epochs(PRODUCT)
    print("=" * 100)
    print(f"MCX PAPER BOT V3 — {PRODUCT}")
    print(f"  strategy_version = {cfg['strategy_version']}")
    print(f"  epoch            = {cfg['epoch']}")
    print(f"  cert_eligible    = {cfg['certification_eligible']}")
    print("=" * 100)

    # Full certification integrity check (product-aware)
    integ = verify_all_epochs_for_product(PRODUCT, STATE_PATH)
    print("=" * 100)
    print("CERTIFICATION INTEGRITY CHECK")
    print("=" * 100)
    print(f"  strategy_version     = {integ['current_version']}")
    print(f"  certification_epoch  = {integ['current_epoch']}")
    print(f"  state_epoch          = {integ['state_epoch']}")
    print(f"  execution_mode       = PAPER")
    print(f"  broker_submission    = false")
    print(f"  live_execution       = false")
    print(f"  CERTIFICATION_INTEGRITY_READY = {integ['certification_ready']}")
    print(f"  CERTIFICATION_ELIGIBLE        = {is_certification_eligible(PRODUCT)}")
    if integ["issues"]:
        print(f"  ISSUES               = {integ['issues']}")
        print(f"  MODE                 = OBSERVATION_ONLY (no entries will certify)")
    print("=" * 100)

    state = load_state()
    save_state(state)  # PATCH A: persist initial state (idempotent)

    # Section 7.27 — startup RECOVERY_ONLY if open position exists
    _recovery_only = False
    if state.get("active_position"):
        _recovery_only = True
        print("=" * 100)
        print("RECOVERY_ONLY MODE — open position detected on startup")
        print(f"  trade_id={state['active_position'].get('trade_id')}")
        print(f"  symbol={state['active_position'].get('symbol')}")
        print("  New entries DISABLED until position terminal + reconciled.")
        print("=" * 100)

    # Section 7.59 — first-trade integrity block
    print("=" * 100)
    print("EXECUTION INTEGRITY PRE-CHECK")
    print("=" * 100)
    print(f"  PRODUCT                {PRODUCT}")
    print(f"  PAPER_MODE             true")
    print(f"  BROKER_SUBMISSION      false")
    print(f"  LIVE_EXECUTION         false")
    print(f"  ENTRY_SOURCE           REAL_DEPTH (REQUIRED)")
    print(f"  EXIT_SOURCE            REAL_DEPTH (REQUIRED)")
    print(f"  SYNTHETIC_EXECUTION    DISABLED")
    print(f"  LTP_FILL               DISABLED")
    print(f"  FIRST_TOUCH_TRACKING   true")
    print(f"  RECONCILIATION_REQ     true")
    print(f"  CERTIFICATION_ELIGIBLE {is_certification_eligible(PRODUCT)}")
    print("=" * 100)
    observation_only = compute_observation_only(PRODUCT, integ["certification_ready"])
    print(f"[state] epoch={state.get('epoch')}  {state['total_trades']}/100  "
          f"P&L=₹{state['total_pnl']:.2f}  obs_only={observation_only}")
    _cfg = get_product_epochs(PRODUCT) or {}
    _ctr = f"{state['total_trades']}/100" if _cfg.get("certification_eligible") else "PRECERT"
    print(f"  CERTIFICATION_ELIGIBLE={_cfg.get('certification_eligible', False)}   CERTIFICATION_COUNTER={_ctr}")

    obj = login()
    if not obj:
        print("LOGIN_FAILED")
        return
    print("✅ Session established")

    # Health check
    print()
    print_health()

    # Pre-session report (context only, no entry authority)
    try:
        _res0 = MCXIdentityResolver().resolve_active(PRODUCT)
        if _res0.get("status") == "OK":
            _tok0 = str(_res0["futures"]["token"])
            _chain0 = build_chain(obj, PRODUCT, window_steps=20)
            _mtf0 = compute_mtf(obj, _tok0, "MCX")
            _ctx0 = fetch_context(PRODUCT)
            _reg0 = classify_regime(_mtf0.get("timeframes", {}), chain=_chain0)
            _prev0 = fetch_previous_session(obj, _tok0, exchange="MCX")
            _cal0 = get_session()
            _exp0 = option_expiry_safety(_chain0.get("expiry"), _res0["futures"].get("expiry"))
            _ev0 = event_get_state()
            _report = ps_build(_chain0, _ctx0, _mtf0, _reg0, _prev0, _cal0, _exp0, _ev0, product=PRODUCT)
            ps_print(_report, product=PRODUCT)
    except Exception as _e:
        print(f"[presession] failed: {str(_e)[:80]}")

    resolver = MCXIdentityResolver()
    stable_pcr = StablePCR(strike_step=PRODUCTS[PRODUCT]["strike_interval"],
                           epoch=integ["current_epoch"])
    price_oi = PriceOITracker()
    history = []

    attempts = 0
    while attempts < MAX_ATTEMPTS:
        attempts += 1

        # Calendar check (replaces market_status)
        cal = get_session()
        print(f"\n{'=' * 100}")
        print(f"Attempt {attempts} | Trades: {state['total_trades']}/100 | "
              f"MCX: {cal['status']} ({cal.get('note', '')})")
        print(f"{'=' * 100}")

        if not cal.get("tradable"):
            if cal["status"] in ("WEEKEND", "HOLIDAY"):
                print(f"  {cal['status']}. Stop.")
                break
            time.sleep(CYCLE_SECONDS)
            continue

        # Resolve identity
        res = resolver.resolve_active(PRODUCT)
        if res["status"] != "OK":
            print(f"  Identity: {res['status']}")
            time.sleep(CYCLE_SECONDS); continue
        fut_token = str(res["futures"]["token"])

        # Build chain + mtf + external
        chain = build_chain(obj, PRODUCT, window_steps=20)
        if chain.get("status") != "OK":
            print(f"  Chain: {chain['status']}")
            time.sleep(CYCLE_SECONDS); continue

        mtf = compute_mtf(obj, fut_token, "MCX")
        ctx = fetch_context(PRODUCT)
        regime = classify_regime(mtf.get("timeframes", {}), chain=chain)

        # Stable PCR — anchor reference to max_pain (spec §2, §11)
        mp = chain.get("max_pain")
        if mp and stable_pcr.reference_strike is None:
            stable_pcr.reference_strike = mp
        elif mp and stable_pcr.reference_strike is not None:
            drift = abs(mp - stable_pcr.reference_strike) / stable_pcr.reference_strike * 100
            if drift >= 1.0:
                stable_pcr.reference_strike = mp
                stable_pcr._prev_call_oi = None
                stable_pcr._prev_put_oi = None
        spcr = stable_pcr.compute(chain)

        ev_state = event_get_state()
        expiry_state = option_expiry_safety(chain.get("expiry"),
                                            res["futures"].get("expiry"))

        # VWAP + structure
        vwap_ctx = session_vwap(obj, fut_token, exchange="MCX")
        structure = compute_structure(mtf, vwap_ctx, chain.get("future_ltp"))

        # Price/OI update
        fq = fetch_full_quote(obj, fut_token)
        fut_ltp = float(fq.get("ltp", 0) or 0) if fq else 0
        # MCX futures OI may arrive under opnInterest instead of oi
        _oi_raw = (fq or {}).get("oi")
        if not _oi_raw:
            _oi_raw = (fq or {}).get("opnInterest")
        if not _oi_raw:
            _oi_raw = (fq or {}).get("openInterest")
        fut_oi = int(_oi_raw or 0)
        poi = price_oi.update(fut_ltp, fut_oi)

        # Data quality gate (spec §5)
        dq_ok, dq_blockers = quality_evaluate(
            mtf=mtf, chain=chain, external=ctx, session=cal,
            identity=res, future_quote=fq,
        )

        # ==== AUDIT OUTPUT (spec §31, reviewer additions) ====

        # Session/calendar block
        print(f"  SESSION:  close={cal.get('close_time')}  cutoff=23:15  "
              f"phase={cal.get('phase', '-')}  note={cal.get('note', '')}")

        # Expiry block
        # Normalize both to YYYY-MM-DD for display consistency
        def _norm_exp(s):
            if not s:
                return "n/a"
            s = str(s).strip()
            for fmt in ("%Y-%m-%d", "%d%b%Y", "%d%b%y"):
                try:
                    return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
                except Exception:
                    continue
            return s

        print(f"  EXPIRY:   opt={_norm_exp(chain.get('expiry'))}  "
              f"fut={_norm_exp(res['futures'].get('expiry'))}  "
              f"DTE={expiry_state.get('days_to_expiry')}  "
              f"devolvement=false  note={expiry_state.get('note')}")

        # Price/OI block with deltas
        _pchg = poi.get('price_chg_pct')
        _ochg = poi.get('oi_chg_pct')
        _pstr = f"{_pchg:+.3f}%" if _pchg is not None else "n/a"
        _ostr = f"{_ochg:+.3f}%" if _ochg is not None else "n/a"
        print(f"  PRICE/OI: price=₹{fut_ltp:.2f} ({_pstr})  oi={fut_oi} ({_ostr})  "
              f"state={poi.get('state')}  reason={poi.get('reason', 'n/a')}")

        # PCR block with CE/PE OI totals
        _chain_contracts = len(chain.get("ce_data", {})) + len(chain.get("pe_data", {}))
        _ce_oi = sum(v.get("oi", 0) for v in chain.get("ce_data", {}).values())
        _pe_oi = sum(v.get("oi", 0) for v in chain.get("pe_data", {}).values())
        _pcr_ema = spcr.get("PCR_EMA_3") if spcr.get("status") == "OK" else "N/A"
        _pcr_ref = spcr.get("reference_strike") if spcr.get("status") == "OK" else None
        _pcr_used = spcr.get("contracts_used") if spcr.get("status") == "OK" else 0
        _pcr_max = spcr.get("max_contracts") if spcr.get("status") == "OK" else 0
        _pcr_uni = spcr.get("universe_strikes") if spcr.get("status") == "OK" else 0
        print(f"  PCR:      raw={chain.get('pcr_oi')} (chain {_chain_contracts} contracts)  "
              f"stable={_pcr_ema}")
        print(f"            ref={_pcr_ref}  strikes={_pcr_uni}  "
              f"ce_contracts={_pcr_uni}  pe_contracts={_pcr_uni}  "
              f"total_contracts={_pcr_used}/{_pcr_max}")
        if _ce_oi > 0:
            print(f"            CE_OI={_ce_oi:,}  PE_OI={_pe_oi:,}  "
                  f"PE/CE={_pe_oi/_ce_oi:.4f}")
        else:
            print(f"            CE_OI=0 (n/a)")

        # Data quality block
        fr = report_freshness(chain=chain, external=ctx, mtf=mtf)
        dq_state = "PASS" if dq_ok else "FAIL"
        print(f"  DQ:       {dq_state}  {freshness_summary(fr)}")
        if not dq_ok:
            print(f"            blockers={dq_blockers}")

        # Regime + event + structure
        print(f"  REGIME:   {regime.get('regime')}(conf={regime.get('confidence')})  "
              f"event={ev_state.get('state')}({event_describe(ev_state)})")
        print(f"  {structure_describe(structure)}")

        # Per-cycle market evidence readiness
        mkt_ready = dq_ok and chain.get("status") == "OK" and mtf.get("status") == "OK"
        print(f"  MARKET_EVIDENCE_READY: {mkt_ready}")

        # Compose decision
        decision = compose_decision(chain, ctx, mtf, regime, vwap_ctx=vwap_ctx,
                                    event_state=ev_state, stable_pcr=spcr)
        print_decision(decision)

        # Setup classification (spec §13)
        setup = classify_setup(decision, regime, structure, mtf, poi.get("state"))
        print(f"  SETUP: {setup_describe(setup)}")

        # Persist decision record
        append_jsonl(DECISIONS_PATH, {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "attempt": attempts,
            "epoch_id": (get_product_epochs(PRODUCT) or {}).get("epoch"),
            "strategy_version": (get_product_epochs(PRODUCT) or {}).get("strategy_version"),
            "certification_eligible": is_certification_eligible(PRODUCT),
            "future_ltp": fut_ltp, "future_oi": fut_oi,
            "pcr_raw": chain.get("pcr_oi"),
            "pcr_stable": spcr.get("PCR_EMA_3") if spcr.get("status") == "OK" else None,
            "regime": regime, "structure": structure, "price_oi": poi,
            "event_state": ev_state, "expiry_state": expiry_state,
            "decision": decision, "setup": setup,
            "data_quality_ok": dq_ok, "data_quality_blockers": dq_blockers,
            "market_phase": cal.get("phase"),
        })

        # Update history
        history.append({"action": decision["action"], "bias": decision["bias"]})
        history = history[-HISTORY_SIZE:]

        # Manage active position
        active = state.get("active_position")
        if active:
            # Section 7.18 — use real bid-side VWAP as executable mark
            mark, mark_q = get_bid_mark_for_position(obj, active, tick=0.05)
            if mark is None:
                print(f"  MARK_EVIDENCE_UNAVAILABLE: {(mark_q or {}).get('rejection_reasons')}")
                save_state(state)
                time.sleep(CYCLE_SECONDS)
                continue
            ltp = mark  # downstream uses "ltp" variable; now it is bid-side VWAP
            # Section 7.21 / P0-A — track first-touch ordering with full persistence
            ft = _restore_first_touch(active)
            now_iso = datetime.now(IST).isoformat()
            ft.ingest(mark, now_iso, quote_id=(mark_q or {}).get("raw_payload_hash"))
            active["first_touch_state"] = ft.to_state()
            active["first_touch_result"] = ft.result()
            entry = active["entry"]
            pnl_pct = ((ltp - entry) / entry) * 100
            active["last_price"] = ltp
            active["last_pnl_pct"] = round(pnl_pct, 2)
            if pnl_pct > active.get("max_profit_pct", 0):
                active["max_profit_pct"] = round(pnl_pct, 2)
            if pnl_pct < active.get("min_profit_pct", 0):
                active["min_profit_pct"] = round(pnl_pct, 2)

            entry_dt = datetime.fromisoformat(active["entry_time"])
            mins = int((datetime.now() - entry_dt).total_seconds() / 60)

            closed = False
            if pnl_pct <= STOP_LOSS_PCT:
                close_and_reconcile(obj, active, "STOP_LOSS", ltp, pnl_pct, state); closed = True
            elif pnl_pct >= T3_PCT:
                close_and_reconcile(obj, active, "T3_50%", ltp, pnl_pct, state); closed = True
            elif pnl_pct >= T2_PCT:
                close_and_reconcile(obj, active, "T2_30%", ltp, pnl_pct, state); closed = True
            elif pnl_pct >= T1_PCT:
                close_and_reconcile(obj, active, "T1_15%", ltp, pnl_pct, state); closed = True
            elif datetime.now().time() >= dtime(23, 10):
                close_and_reconcile(obj, active, "MCX_CLOSE_2310", ltp, pnl_pct, state); closed = True
            else:
                should_exit, reason, new_stop = pm_evaluate_exit(
                    active, ltp, decision, regime, mins)
                if should_exit:
                    close_and_reconcile(obj, active, reason, ltp, pnl_pct, state); closed = True
                else:
                    if new_stop and new_stop > active.get("stop_loss", 0):
                        active["stop_loss"] = new_stop
                    print(f"  holding {active['type']} {active['strike']:.0f}  "
                          f"ltp=₹{ltp:.2f}  pnl={pnl_pct:+.2f}%  "
                          f"MFE={active.get('max_profit_pct')}%  "
                          f"SL=₹{active.get('stop_loss')}  min={mins}")
            if not closed:
                save_state(state)
        else:
            # Entry logic
            if not dq_ok:
                print(f"  NO_TRADE_DATA_QUALITY: {dq_blockers}")
            elif observation_only:
                print(f"  OBSERVATION_ONLY — entry suppressed (epoch integrity not ready)")
            elif _recovery_only:
                print(f"  RECOVERY_ONLY — new entries suppressed until open position reconciled")
            elif decision["action"] in ("BUY_CALL", "BUY_PUT") and signals_agree(history, decision["action"]):
                pos = try_open(obj, chain, mtf, ctx, decision, regime, structure, setup, state)
                if pos:
                    state["active_position"] = pos
                    save_state(state)
                else:
                    print("  entry conditions met but no eligible strike")
            else:
                calls = sum(1 for h in history if h["action"] == "BUY_CALL")
                puts = sum(1 for h in history if h["action"] == "BUY_PUT")
                print(f"  No entry. persistence CALL={calls}/3 PUT={puts}/3")

        save_state(state)
        time.sleep(CYCLE_SECONDS)

    save_state(state)
    print(f"\n{'=' * 100}")
    print(f"MCX PAPER BOT V3 stopped. Attempts={attempts} Trades={state['total_trades']}/100 "
          f"P&L=₹{state['total_pnl']:.2f}")
    print(f"{'=' * 100}")
    print()
    cert_print(state)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")

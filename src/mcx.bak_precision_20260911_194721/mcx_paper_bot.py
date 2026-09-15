"""MCX PAPER trading bot — CRUDEOILM. NO live orders. NO broker writes.
Runs one attempt per cycle (default 60s). Tracks one open position at a time.
Persists state + outcome ledger under data/paper_trades/.
"""
import json
import os
import sys
import time
from datetime import datetime, time as dtime

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
from mcx.mcx_bias import compose
from mcx.mcx_strike import select_strike
from mcx.mcx_capital import compute_paper_fill, compute_lots, compute_net_pnl

load_dotenv()

PRODUCT = "CRUDEOILM"
STATE_PATH = f"data/paper_trades/mcx_{PRODUCT.lower()}_experimental.json"
PREDICTIONS_PATH = f"data/paper_trades/mcx_{PRODUCT.lower()}_predictions.jsonl"
OUTCOMES_PATH = f"data/paper_trades/mcx_{PRODUCT.lower()}_outcomes.jsonl"

# Risk parameters (per blueprint §15 — PROVISIONAL, tune after 30+ trades)
STOP_LOSS_PCT = -8.0
T1_PCT = 15.0
T2_PCT = 30.0
T3_PCT = 50.0
MAX_ATTEMPTS = 1000
CYCLE_SECONDS = 60
DEPLOYABLE_CAPITAL = 100_000


def login():
    api_key = os.getenv("ANGEL_API_KEY")
    user_id = os.getenv("ANGEL_USER_ID")
    password = os.getenv("ANGEL_PASSWORD")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")
    if not all([api_key, user_id, password, totp_secret]):
        print("MISSING_ENV")
        return None
    obj = SmartConnect(api_key=api_key)
    resp = obj.generateSession(clientCode=user_id, password=password,
                               totp=pyotp.TOTP(totp_secret).now())
    return obj if resp and resp.get("status") else None


def load_state():
    if not os.path.exists(STATE_PATH):
        return {
            "product": PRODUCT,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "active_position": None,
            "completed_trades": [],
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


def market_status():
    now = datetime.now()
    wd = now.weekday()
    t = now.time()
    if wd >= 5:
        return "WEEKEND", False
    if t < dtime(9, 0):
        return "PRE_OPEN", False
    if t >= dtime(23, 15):
        return "CLOSE_BUFFER", False
    if t >= dtime(23, 30):
        return "CLOSED", False
    return "OPEN", True


def fetch_ltp(obj, token):
    try:
        r = obj.getMarketData("FULL", {"MCX": [str(token)]})
        if r and r.get("data"):
            for row in r["data"].get("fetched", []):
                if str(row.get("symbolToken")) == str(token):
                    return float(row.get("ltp", 0) or 0)
    except Exception:
        pass
    return 0.0


def try_open_position(obj, chain, mtf, ctx, bias, state):
    if bias["bias"] not in ("BULLISH", "BEARISH"):
        return None
    sel = select_strike(chain, bias["bias"])
    if not sel:
        return None

    bid, ask = 0, 0
    fill, status = compute_paper_fill(bid, ask, sel["ltp"], direction="BUY")
    if fill is None:
        return None

    lots, one_lot_cash, _ = compute_lots(fill, PRODUCT, DEPLOYABLE_CAPITAL)
    if lots < 1:
        print(f"  [open] CAPITAL_INSUFFICIENT (one_lot=₹{one_lot_cash:.2f})")
        return None

    pos = {
        "trade_id": f"MCX_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "product": PRODUCT,
        "type": sel["type"],
        "strike": sel["strike"],
        "token": sel["token"],
        "symbol": sel["symbol"],
        "entry": fill,
        "entry_ltp": sel["ltp"],
        "lots": lots,
        "lot_size": PRODUCTS[PRODUCT]["trading_unit"],
        "cash_multiplier": PRODUCTS[PRODUCT]["cash_multiplier"],
        "entry_time": datetime.now().isoformat(timespec="seconds"),
        "stop_loss": round(fill * (1 + STOP_LOSS_PCT / 100), 2),
        "t1": round(fill * (1 + T1_PCT / 100), 2),
        "t2": round(fill * (1 + T2_PCT / 100), 2),
        "t3": round(fill * (1 + T3_PCT / 100), 2),
        "bias_at_entry": bias["bias"],
        "bias_confidence": bias["confidence"],
        "rank_score": sel["score"],
        "reasons": sel["reasons"],
        "max_profit_pct": 0.0,
        "min_profit_pct": 0.0,
    }

    print(f"\n{'=' * 60}")
    print(f"📊 MCX PAPER — {pos['trade_id']}")
    print(f"  {pos['type']} {pos['strike']:.0f}  ({pos['symbol']})")
    print(f"  entry=₹{fill:.2f}  lots={lots}  lot_size={pos['lot_size']}  mult={pos['cash_multiplier']}")
    print(f"  SL=₹{pos['stop_loss']:.2f}  T1=₹{pos['t1']:.2f}  T2=₹{pos['t2']:.2f}  T3=₹{pos['t3']:.2f}")
    print(f"  one_lot_cash=₹{one_lot_cash:.2f}")
    print(f"{'=' * 60}")

    append_jsonl(PREDICTIONS_PATH, {
        "timestamp": pos["entry_time"],
        "trade_id": pos["trade_id"],
        "market": "MCX",
        "product": PRODUCT,
        "bias": bias["bias"],
        "confidence": bias["confidence"],
        "bull_score": bias["bull_score"],
        "bear_score": bias["bear_score"],
        "votes": bias["votes"],
        "selected": {k: pos[k] for k in ("type", "strike", "token", "symbol", "entry", "lots")},
        "chain_pcr": chain.get("pcr_oi"),
        "chain_max_pain": chain.get("max_pain"),
        "mtf_aggregate": mtf.get("aggregate_trend"),
        "external_regime": ctx.get("composite_regime"),
    })

    return pos


def monitor_position(obj, pos):
    """Single-pass check: fetch current LTP, apply exit rules, return exit reason or None."""
    ltp = fetch_ltp(obj, pos["token"])
    if ltp <= 0:
        return None
    entry = pos["entry"]
    pnl_pct = ((ltp - entry) / entry) * 100

    if pnl_pct > pos.get("max_profit_pct", 0):
        pos["max_profit_pct"] = round(pnl_pct, 2)
    if pnl_pct < pos.get("min_profit_pct", 0):
        pos["min_profit_pct"] = round(pnl_pct, 2)

    pos["last_price"] = ltp
    pos["last_pnl_pct"] = round(pnl_pct, 2)
    pos["last_check"] = datetime.now().isoformat(timespec="seconds")

    # Exit rules (in order)
    if pnl_pct <= STOP_LOSS_PCT:
        return "STOP_LOSS", ltp, pnl_pct
    if pnl_pct >= T3_PCT:
        return "T3_50%", ltp, pnl_pct
    if pnl_pct >= T2_PCT:
        return "T2_30%", ltp, pnl_pct
    if pnl_pct >= T1_PCT:
        return "T1_15%", ltp, pnl_pct
    # Time-based: force close at 23:10 IST
    now_t = datetime.now().time()
    if now_t >= dtime(23, 10):
        return "MCX_CLOSE_2310", ltp, pnl_pct
    return None


def close_position(obj, pos, exit_reason, exit_ltp, exit_pnl_pct, state):
    bid, ask = 0, 0
    fill, _ = compute_paper_fill(bid, ask, exit_ltp, direction="SELL")
    if fill is None:
        fill = exit_ltp

    net = compute_net_pnl(pos["entry"], fill, pos["lots"], PRODUCT, direction="BUY")
    pos["exit"] = fill
    pos["exit_time"] = datetime.now().isoformat(timespec="seconds")
    pos["exit_reason"] = exit_reason
    pos["exit_pnl_pct_pre_costs"] = round(exit_pnl_pct, 2)
    pos.update(net)

    # Update state
    state["total_trades"] += 1
    if net["net_pnl"] > 0:
        state["winning_trades"] += 1
    elif net["net_pnl"] < 0:
        state["losing_trades"] += 1
    state["total_pnl"] = round(state["total_pnl"] + net["net_pnl"], 2)
    state["completed_trades"].append(pos)
    state["active_position"] = None

    append_jsonl(OUTCOMES_PATH, pos)

    print(f"\n{'=' * 60}")
    print(f"📊 Position Closed: {exit_reason}")
    print(f"  {pos['type']} {pos['strike']:.0f}  entry=₹{pos['entry']:.2f} → exit=₹{fill:.2f}")
    print(f"  Gross=₹{net['gross_pnl']:.2f}  Costs=₹{net['costs_total']:.2f}  NET=₹{net['net_pnl']:.2f} ({net['net_pnl_pct']}%)")
    print(f"  Total P&L: ₹{state['total_pnl']:.2f}")
    print(f"  Progress: {state['total_trades']}/100  Wins={state['winning_trades']}  Losses={state['losing_trades']}")
    print(f"{'=' * 60}")


def main():
    print("=" * 80)
    print(f"MCX PAPER BOT — {PRODUCT}")
    print("=" * 80)

    state = load_state()
    print(f"State loaded: {state['total_trades']} trades, ₹{state['total_pnl']:.2f} P&L")

    obj = login()
    if not obj:
        print("LOGIN_FAILED")
        return
    print("✅ Session established")

    resolver = MCXIdentityResolver()
    attempts = 0
    while attempts < MAX_ATTEMPTS:
        attempts += 1
        status, tradable = market_status()
        print(f"\n{'=' * 80}")
        print(f"Attempt {attempts} | Trades: {state['total_trades']}/100 | MCX: {status}")
        print(f"{'=' * 80}")

        if not tradable:
            print(f"  Market not tradable ({status}). Sleeping.")
            if status in ("CLOSED", "WEEKEND"):
                break
            time.sleep(CYCLE_SECONDS)
            continue

        # Identity + chain + mtf + ctx
        res = resolver.resolve_active(PRODUCT)
        if res["status"] != "OK":
            print(f"  Identity: {res['status']}")
            time.sleep(CYCLE_SECONDS)
            continue

        fut_token = str(res["futures"]["token"])
        chain = build_chain(obj, PRODUCT, window_steps=10)
        if chain.get("status") != "OK":
            print(f"  Chain: {chain['status']}")
            time.sleep(CYCLE_SECONDS)
            continue

        mtf = compute_mtf(obj, fut_token, "MCX")
        ctx = fetch_context(PRODUCT)

        bias = compose(chain, ctx, mtf)
        print(f"  future_ltp=₹{chain['future_ltp']:.2f}  atm={chain['atm']:.0f}  "
              f"pcr={chain['pcr_oi']}  maxpain={chain['max_pain']}")
        print(f"  mtf={mtf.get('aggregate_trend')}  ext={ctx.get('composite_regime')}  "
              f"→ BIAS: {bias['bias']} ({bias['confidence']}) {bias['action']}")

        # If position open — monitor it
        active = state.get("active_position")
        if active:
            exit_info = monitor_position(obj, active)
            if exit_info:
                reason, ltp, pnl_pct = exit_info
                close_position(obj, active, reason, ltp, pnl_pct, state)
            else:
                print(f"  holding {active['type']} {active['strike']:.0f}  "
                      f"ltp=₹{active.get('last_price')}  pnl={active.get('last_pnl_pct')}%")
            save_state(state)
        else:
            # Try to open
            if bias["action"] in ("BUY_CALL", "BUY_PUT"):
                pos = try_open_position(obj, chain, mtf, ctx, bias, state)
                if pos:
                    state["active_position"] = pos
                    save_state(state)
                else:
                    print("  No eligible strike opened")
            else:
                print(f"  No entry (bias={bias['bias']})")

        save_state(state)
        time.sleep(CYCLE_SECONDS)

    # Final save
    save_state(state)
    print(f"\n{'=' * 80}")
    print(f"MCX PAPER BOT stopped.")
    print(f"  Attempts: {attempts}")
    print(f"  Trades: {state['total_trades']}/100")
    print(f"  Total P&L: ₹{state['total_pnl']:.2f}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")

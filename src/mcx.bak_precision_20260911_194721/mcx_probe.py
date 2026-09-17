"""MCX live probe — READ ONLY. No trades. No ledger writes.
Proves data flows from Angel One for CRUDEOILM futures + options.
"""
import os
import sys
from datetime import date, datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from dotenv import load_dotenv
import pyotp
from SmartApi import SmartConnect

from mcx.mcx_contracts import ANGEL_MASTER_SCALE, PRODUCTS
from mcx.mcx_identity import MCXIdentityResolver

load_dotenv()


def _f(v, default=0.0):
    try:
        return float(v or 0)
    except Exception:
        return default


def _i(v, default=0):
    try:
        return int(v or 0)
    except Exception:
        return default


def login():
    api_key = os.getenv("ANGEL_API_KEY")
    user_id = os.getenv("ANGEL_USER_ID")
    password = os.getenv("ANGEL_PASSWORD")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")

    if not all([api_key, user_id, password, totp_secret]):
        print("MISSING_ENV — check ANGEL_API_KEY / USER_ID / PASSWORD / TOTP_SECRET")
        return None

    obj = SmartConnect(api_key=api_key)
    totp = pyotp.TOTP(totp_secret).now()
    resp = obj.generateSession(clientCode=user_id, password=password, totp=totp)
    if not resp or not resp.get("status"):
        print(f"LOGIN_FAILED: {resp}")
        return None
    print("✅ Angel session established")
    return obj


def fetch_full(obj, tokens):
    """One getMarketData(FULL) call for a list of MCX tokens."""
    if not tokens:
        return {}
    try:
        resp = obj.getMarketData("FULL", {"MCX": [str(t) for t in tokens]})
    except Exception as e:
        print(f"  [getMarketData err] {str(e)[:100]}")
        return {}
    if not resp or not resp.get("data"):
        return {}
    fetched = resp["data"].get("fetched") or []
    out = {}
    for row in fetched:
        out[str(row.get("symbolToken", ""))] = row
    return out


def print_option_row(label, master_rec, quote_row, atm_strike):
    if not quote_row:
        print(f"  {label:<22} NO_QUOTE")
        return
    ltp = _f(quote_row.get("ltp"))
    oi = _i(quote_row.get("oi", quote_row.get("opnInterest")))
    vol = _i(quote_row.get("volume", quote_row.get("tradeVolume")))
    bid = _f(quote_row.get("bid"))
    ask = _f(quote_row.get("ask"))
    # bestFive fallback
    if bid <= 0:
        bb = quote_row.get("bestFiveBuyData") or []
        if bb and isinstance(bb, list) and bb[0]:
            bid = _f(bb[0].get("price"))
    if ask <= 0:
        bs = quote_row.get("bestFiveSellData") or []
        if bs and isinstance(bs, list) and bs[0]:
            ask = _f(bs[0].get("price"))
    spread_pct = ((ask - bid) / ltp * 100) if (bid > 0 and ask > 0 and ltp > 0) else None
    strike = _f(master_rec.get("strike")) / ANGEL_MASTER_SCALE
    dist = strike - atm_strike
    spread_str = f"{spread_pct:.2f}%" if spread_pct is not None else "N/A"
    print(f"  {label:<22} sym={master_rec.get('symbol'):<32} "
          f"strike={strike:>7.0f} d={dist:>+6.0f} "
          f"ltp={ltp:>8.2f} bid={bid:>8.2f} ask={ask:>8.2f} "
          f"spread={spread_str:>7} oi={oi:>7} vol={vol:>8}")


def main():
    print("=" * 100)
    print("MCX PROBE — read only, no trades")
    print("=" * 100)

    obj = login()
    if obj is None:
        return

    product = "CRUDEOILM"
    spec = PRODUCTS[product]
    print(f"\nProduct: {product} ({spec['display_name']})")
    print(f"  trading_unit={spec['trading_unit']}  cash_multiplier={spec['cash_multiplier']}  "
          f"tick={spec['tick_size']}  strike_step={spec['strike_interval']}")

    resolver = MCXIdentityResolver()
    res = resolver.resolve_active(product)
    print(f"\nIdentity: status={res['status']}")
    if res["status"] != "OK" or not res["futures"]:
        print("Identity unavailable. Stop.")
        return

    fut = res["futures"]
    fut_token = str(fut["token"])
    print(f"  active_future={fut['symbol']} token={fut_token} exp={fut['expiry']}")
    print(f"  option_expiry={res['option_expiry']}")

    # Fetch future quote
    print(f"\nFetching futures quote ...")
    fut_quotes = fetch_full(obj, [fut_token])
    fq = fut_quotes.get(fut_token)
    if not fq:
        print("  FUTURE NO_QUOTE — full response:")
        try:
            raw = obj.getMarketData("FULL", {"MCX": [fut_token]})
            print(f"  {str(raw)[:400]}")
        except Exception as e:
            print(f"  {e}")
        return

    fut_ltp = _f(fq.get("ltp"))
    fut_oi = _i(fq.get("oi", fq.get("opnInterest")))
    fut_vol = _i(fq.get("volume", fq.get("tradeVolume")))
    print(f"  {fut['symbol']:<24} ltp=₹{fut_ltp:.2f}  oi={fut_oi}  vol={fut_vol}")
    if fut_ltp <= 0:
        print("  future ltp=0, cannot derive ATM. Stop.")
        return

    # Determine ATM strike (round to strike_interval)
    step = spec["strike_interval"]
    atm = round(fut_ltp / step) * step
    print(f"\n  Derived ATM strike: ₹{atm:.0f} (spot ₹{fut_ltp:.2f}, step ₹{step})")

    # Pick 5 CE + 5 PE around ATM (±2 steps)
    calls = res["calls"]
    puts = res["puts"]
    offsets = [-2, -1, 0, 1, 2]
    pick_strikes = [atm + o * step for o in offsets]

    ce_recs = [(s, calls[s]) for s in pick_strikes if s in calls]
    pe_recs = [(s, puts[s]) for s in pick_strikes if s in puts]

    all_tokens = [str(r["token"]) for _, r in ce_recs] + [str(r["token"]) for _, r in pe_recs]
    print(f"\nFetching {len(all_tokens)} option quotes in one batched call ...")
    opt_quotes = fetch_full(obj, all_tokens)
    print(f"  received={len(opt_quotes)}/{len(all_tokens)}")

    print(f"\n  --- CE side (strikes around ATM ₹{atm:.0f}) ---")
    for strike, rec in ce_recs:
        print_option_row("CE", rec, opt_quotes.get(str(rec["token"])), atm)

    print(f"\n  --- PE side ---")
    for strike, rec in pe_recs:
        print_option_row("PE", rec, opt_quotes.get(str(rec["token"])), atm)

    print(f"\n{'=' * 100}")
    print(f"PROBE COMPLETE. As of {datetime.now().isoformat(timespec='seconds')}")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    main()

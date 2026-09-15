"""MCX option chain snapshot + basic analytics. READ-ONLY.
Mirrors the OI/PCR/max-pain concepts used for NIFTY, adapted for MCX.
"""
import os
import sys
from datetime import datetime

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


def _f(v, d=0.0):
    try: return float(v or 0)
    except: return d

def _i(v, d=0):
    try: return int(v or 0)
    except: return d


def login():
    api_key = os.getenv("ANGEL_API_KEY")
    user_id = os.getenv("ANGEL_USER_ID")
    password = os.getenv("ANGEL_PASSWORD")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")
    if not all([api_key, user_id, password, totp_secret]):
        print("MISSING_ENV"); return None
    obj = SmartConnect(api_key=api_key)
    resp = obj.generateSession(client_user_id if False else user_id, password, pyotp.TOTP(totp_secret).now()) if False else obj.generateSession(clientCode=user_id, password=password, totp=pyotp.TOTP(totp_secret).now())
    if not resp or not resp.get("status"):
        print(f"LOGIN_FAILED: {resp}"); return None
    return obj


def fetch_full(obj, tokens):
    if not tokens: return {}
    out = {}
    CHUNK = 50
    for i in range(0, len(tokens), CHUNK):
        try:
            resp = obj.getMarketData("FULL", {"MCX": [str(t) for t in tokens[i:i+CHUNK]]})
        except Exception as e:
            print(f"  [getMarketData err chunk {i}] {str(e)[:80]}")
            continue
        if resp and resp.get("data"):
            for row in resp["data"].get("fetched", []):
                out[str(row.get("symbolToken",""))] = row
    return out


def build_chain(obj, product, window_steps=10):
    spec = PRODUCTS[product]
    step = spec["strike_interval"]

    resolver = MCXIdentityResolver()
    res = resolver.resolve_active(product)
    if res["status"] != "OK":
        return {"status": res["status"]}

    fut_tok = str(res["futures"]["token"])
    fq = fetch_full(obj, [fut_tok]).get(fut_tok)
    if not fq:
        return {"status": "FUTURE_NO_QUOTE"}
    fut_ltp = _f(fq.get("ltp"))
    if fut_ltp <= 0:
        return {"status": "FUTURE_LTP_ZERO"}

    atm = round(fut_ltp / step) * step
    strikes = [atm + i * step for i in range(-window_steps, window_steps + 1)]

    calls = res["calls"]; puts = res["puts"]
    ce_recs = [calls[s] for s in strikes if s in calls]
    pe_recs = [puts[s] for s in strikes if s in puts]
    all_toks = [str(r["token"]) for r in ce_recs + pe_recs]
    quotes = fetch_full(obj, all_toks)

    ce_data = {}
    pe_data = {}
    for r in ce_recs:
        s = _f(r.get("strike")) / ANGEL_MASTER_SCALE
        q = quotes.get(str(r["token"]))
        if q:
            ce_data[s] = {
                "symbol": r["symbol"], "token": r["token"],
                "ltp": _f(q.get("ltp")), "oi": _i(q.get("oi", q.get("opnInterest"))),
                "vol": _i(q.get("volume", q.get("tradeVolume"))),
            }
    for r in pe_recs:
        s = _f(r.get("strike")) / ANGEL_MASTER_SCALE
        q = quotes.get(str(r["token"]))
        if q:
            pe_data[s] = {
                "symbol": r["symbol"], "token": r["token"],
                "ltp": _f(q.get("ltp")), "oi": _i(q.get("oi", q.get("opnInterest"))),
                "vol": _i(q.get("volume", q.get("tradeVolume"))),
            }

    total_ce_oi = sum(v["oi"] for v in ce_data.values())
    total_pe_oi = sum(v["oi"] for v in pe_data.values())
    pcr_oi = round(total_pe_oi / total_ce_oi, 4) if total_ce_oi > 0 else None

    all_strikes = sorted(set(list(ce_data.keys()) + list(pe_data.keys())))
    max_pain = None
    if all_strikes:
        pain_by_strike = []
        for test in all_strikes:
            total = 0
            for s, ce in ce_data.items():
                if test > s: total += (test - s) * ce["oi"]
            for s, pe in pe_data.items():
                if test < s: total += (s - test) * pe["oi"]
            pain_by_strike.append((test, total))
        if pain_by_strike:
            max_pain = min(pain_by_strike, key=lambda x: x[1])[0]

    top_ce = sorted(ce_data.items(), key=lambda x: x[1]["oi"], reverse=True)[:3]
    top_pe = sorted(pe_data.items(), key=lambda x: x[1]["oi"], reverse=True)[:3]

    return {
        "status": "OK",
        "product": product,
        "expiry": res["option_expiry"],
        "future": res["futures"]["symbol"],
        "future_ltp": fut_ltp,
        "atm": atm,
        "ce_data": ce_data, "pe_data": pe_data,
        "pcr_oi": pcr_oi,
        "max_pain": max_pain,
        "resistance": [s for s, _ in top_ce],
        "support": [s for s, _ in top_pe],
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def print_chain(chain):
    print(f"\n{chain['product']}  expiry={chain['expiry']}")
    print(f"future={chain['future']}  ltp=₹{chain['future_ltp']:.2f}  ATM={chain['atm']:.0f}")
    print(f"PCR_OI={chain['pcr_oi']}  MaxPain={chain['max_pain']}")
    print(f"Resistance(top CE OI)={chain['resistance']}")
    print(f"Support(top PE OI)   ={chain['support']}")
    print(f"\n{'strike':>8} {'CE ltp':>10} {'CE oi':>10} {'CE vol':>10}  |  {'PE ltp':>10} {'PE oi':>10} {'PE vol':>10}")
    print("-" * 90)
    strikes = sorted(set(list(chain["ce_data"].keys()) + list(chain["pe_data"].keys())))
    for s in strikes:
        ce = chain["ce_data"].get(s, {})
        pe = chain["pe_data"].get(s, {})
        print(f"{s:>8.0f} {ce.get('ltp',0):>10.2f} {ce.get('oi',0):>10} {ce.get('vol',0):>10}  |  "
              f"{pe.get('ltp',0):>10.2f} {pe.get('oi',0):>10} {pe.get('vol',0):>10}")


if __name__ == "__main__":
    print("=" * 90)
    print("MCX CHAIN SNAPSHOT — read only")
    print("=" * 90)
    obj = login()
    if not obj:
        sys.exit(1)
    print("✅ Angel session established")
    for prod in ["CRUDEOILM"]:
        c = build_chain(obj, prod, window_steps=10)
        if c["status"] == "OK":
            print_chain(c)
        else:
            print(f"\n{prod}: {c['status']}")

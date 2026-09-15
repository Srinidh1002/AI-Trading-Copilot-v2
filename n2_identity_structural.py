"""N2.1 - Structural identity from data/instruments.json. Offline."""
import json
from datetime import datetime

with open("data/instruments.json", encoding="utf-8") as f:
    raw = json.load(f)

# Angel's instrument master is a list of records
records = raw if isinstance(raw, list) else raw.get("data", [])

def find_spot(symbol, exchange):
    return [r for r in records
            if r.get("symbol") == symbol
            and r.get("exch_seg") == exchange
            and r.get("instrumenttype", "").upper() in ("", "AMXIDX", "INDEX")]

def find_options(symbol, exchange, expiry_filter=None):
    out = []
    for r in records:
        if r.get("name") != symbol: continue
        if r.get("exch_seg") != exchange: continue
        it = (r.get("instrumenttype") or "").upper()
        if it not in ("OPTIDX", "OPTSTK", ""): continue
        if "CE" not in (r.get("symbol") or "") and "PE" not in (r.get("symbol") or ""):
            continue
        if expiry_filter and r.get("expiry") != expiry_filter: continue
        out.append(r)
    return out

print("=" * 90)
print("N2.1 - STRUCTURAL IDENTITY FROM INSTRUMENT MASTER")
print("=" * 90)

# NIFTY spot
print("\n[NIFTY spot]")
for r in find_spot("NIFTY", "NSE")[:3]:
    print(f"  symbol={r.get('symbol')} token={r.get('token')} exchange={r.get('exch_seg')}")

# SENSEX spot
print("\n[SENSEX spot]")
for r in find_spot("SENSEX", "BSE")[:3]:
    print(f"  symbol={r.get('symbol')} token={r.get('token')} exchange={r.get('exch_seg')}")

# Current NIFTY expiries
nifty_opts = [r for r in records if r.get("name") == "NIFTY" and r.get("exch_seg") == "NFO" and r.get("instrumenttype") == "OPTIDX"]
nifty_exp = sorted({r.get("expiry") for r in nifty_opts if r.get("expiry")})
print(f"\n[NIFTY option expiries present in master] {len(nifty_exp)} total")
for e in nifty_exp[:6]:
    print(f"  {e}")

# Current SENSEX expiries
sensex_opts = [r for r in records if r.get("name") == "SENSEX" and r.get("exch_seg") == "BFO" and r.get("instrumenttype") == "OPTIDX"]
sensex_exp = sorted({r.get("expiry") for r in sensex_opts if r.get("expiry")})
print(f"\n[SENSEX option expiries present in master] {len(sensex_exp)} total")
for e in sensex_exp[:6]:
    print(f"  {e}")

# Sample NIFTY ATM options
if nifty_exp:
    near = nifty_exp[0]  # earliest
    print(f"\n[Sample NIFTY options for expiry {near}]")
    sample = [r for r in nifty_opts if r.get("expiry") == near][:5]
    for r in sample:
        print(f"  {r.get('symbol')}  token={r.get('token')}  strike={r.get('strike')}")

# Sample SENSEX ATM options
if sensex_exp:
    near = sensex_exp[0]
    print(f"\n[Sample SENSEX options for expiry {near}]")
    sample = [r for r in sensex_opts if r.get("expiry") == near][:5]
    for r in sample:
        print(f"  {r.get('symbol')}  token={r.get('token')}  strike={r.get('strike')}")

print("\nDone.")

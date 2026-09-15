"""N2.2 - Live spot identity check via Angel provider."""
import os, sys
from datetime import datetime
sys.path.append("src")
from dotenv import load_dotenv
import pyotp
from SmartApi import SmartConnect

load_dotenv()

def login():
    obj = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
    r = obj.generateSession(
        clientCode=os.getenv("ANGEL_USER_ID"),
        password=os.getenv("ANGEL_PASSWORD"),
        totp=pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now(),
    )
    if not (r and r.get("status")):
        raise SystemExit("LOGIN_FAILED")
    return obj

obj = login()
print("Session established:", datetime.now().isoformat())
print()

# Live spots
for label, exch, sym, tok in [
    ("NIFTY  NSE",     "NSE", "NIFTY",  "99926000"),
    ("SENSEX BSE live","BSE", "SENSEX", "1"),
    ("SENSEX BSE hist","BSE", "SENSEX", "99919000"),
]:
    try:
        r = obj.ltpData(exch, sym, tok)
        if r and r.get("data"):
            d = r["data"]
            print(f"[{label}] ltp={d.get('ltp')}  exch={d.get('exchange')}  token={d.get('symbolToken')}  ts={d.get('exchange_timestamp')}")
        else:
            print(f"[{label}] EMPTY response: {r}")
    except Exception as e:
        print(f"[{label}] ERROR: {str(e)[:80]}")

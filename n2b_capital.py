"""N2B - capital affordability check. Read-only. Uses bot's own methods."""
import sys
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot

DEPLOYABLE = 100000  # from CapitalEngine(deployable_capital=100000)

for market in ("NIFTY", "SENSEX"):
    print("=" * 90)
    print(f"{market}")
    print("=" * 90)
    b = UnifiedTradingBot(market)
    b.connect_with_retry()
    b.load_instruments()

    spot = b.get_spot()
    expiry = b.get_expiry()
    print(f"  spot   = {spot:.2f}")
    print(f"  expiry = {expiry}")

    options, atm = b.get_options(spot, expiry)
    print(f"  atm    = {atm}")
    print(f"  chain options returned = {len(options)}")
    print(f"  deployable capital = {DEPLOYABLE}")

    # Show top candidates nearest to ATM
    if options:
        # Sort by distance from atm
        sorted_opts = sorted(options, key=lambda o: abs(float(o.get("strike", 0)) - atm))
        print()
        print(f"  {'strike':>8} {'type':<4} {'ltp':>10} {'bid':>10} {'ask':>10} {'1lot_cost':>12} {'afford':>8}")
        print("  " + "-" * 68)
        for opt in sorted_opts[:6]:
            strike = float(opt.get("strike", 0))
            typ = opt.get("type", "?")
            ltp = float(opt.get("ltp", 0) or 0)
            bid = opt.get("bid")
            ask = opt.get("ask")
            # Use ask (executable) for cost if available, else ltp
            exec_px = float(ask) if ask else ltp
            one_lot = exec_px * b.lot_size
            afford = int(DEPLOYABLE // one_lot) if one_lot > 0 else 0
            print(f"  {strike:>8.0f} {typ:<4} {ltp:>10.2f} "
                  f"{(bid if bid else 0):>10.2f} {(ask if ask else 0):>10.2f} "
                  f"{one_lot:>12.2f} {afford:>8}")

    print()

# Also test alternate NIFTY token (finding F-N2-A)
print("=" * 90)
print("NIFTY spot token cross-check")
print("=" * 90)
import os
from dotenv import load_dotenv
import pyotp
from SmartApi import SmartConnect
load_dotenv()
obj = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
obj.generateSession(
    clientCode=os.getenv("ANGEL_USER_ID"),
    password=os.getenv("ANGEL_PASSWORD"),
    totp=pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now(),
)
for tok in ("99926000", "26000"):
    try:
        r = obj.ltpData("NSE", "NIFTY", tok)
        ltp = r.get("data", {}).get("ltp") if r and r.get("data") else None
        print(f"  token={tok:<12} -> ltp={ltp}")
    except Exception as e:
        print(f"  token={tok:<12} -> ERROR: {str(e)[:60]}")

"""MCX combined snapshot — single-screen market read. READ-ONLY.
Composes: identity + chain + external context for one product.
Does NOT produce a trade decision (that's MCX-05+).
"""
import os
import sys
from datetime import datetime, time as dtime

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from dotenv import load_dotenv
import pyotp
from SmartApi import SmartConnect

from mcx.mcx_chain import build_chain, print_chain
from mcx.mcx_external_context import fetch_context, print_context

load_dotenv()


def login():
    api_key = os.getenv("ANGEL_API_KEY")
    user_id = os.getenv("ANGEL_USER_ID")
    password = os.getenv("ANGEL_PASSWORD")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")
    if not all([api_key, user_id, password, totp_secret]):
        print("MISSING_ENV"); return None
    obj = SmartConnect(api_key=api_key)
    resp = obj.generateSession(clientCode=user_id, password=password,
                               totp=pyotp.TOTP(totp_secret).now())
    if not resp or not resp.get("status"):
        print(f"LOGIN_FAILED: {resp}"); return None
    return obj


def market_status():
    """MCX Crude Oil session check (approximate — official calendar would refine)."""
    now = datetime.now().time()
    # Simplified: 09:00 – 23:30 IST (Mon–Fri). Full calendar at MCX-03.
    if now < dtime(9, 0):
        return "PRE_OPEN", False
    if now > dtime(23, 30):
        return "CLOSED", False
    wd = datetime.now().weekday()
    if wd >= 5:
        return "WEEKEND", False
    return "OPEN", True


def read_summary(chain, ctx):
    """Non-decision summary of what each layer is saying."""
    rows = []

    # Chain reads
    if chain.get("status") == "OK":
        pcr = chain.get("pcr_oi")
        mp = chain.get("max_pain")
        atm = chain.get("atm")
        f = chain.get("future_ltp")

        pcr_read = "NEUTRAL"
        if pcr is not None:
            if pcr > 1.3:   pcr_read = "BULLISH (contrarian, high put writing)"
            elif pcr < 0.7: pcr_read = "BEARISH (contrarian, high call writing)"
            elif pcr > 1.1: pcr_read = "WEAK_BULLISH"
            elif pcr < 0.9: pcr_read = "WEAK_BEARISH"

        pin = "PINNED_TO_ATM"
        if mp and atm:
            if abs(mp - atm) > 100:
                pin = f"DRIFT (max_pain ₹{mp:.0f} vs ATM ₹{atm:.0f})"

        rows.append(("Chain PCR_OI", f"{pcr}", pcr_read))
        rows.append(("Max Pain vs ATM", f"₹{mp:.0f} vs ₹{atm:.0f}", pin))

    # External context
    if ctx.get("status") == "OK":
        rows.append(("External composite", f"{ctx.get('composite_move_1d_pct')}%",
                     ctx.get("composite_regime", "UNKNOWN")))
        for label, d in ctx.get("primary", {}).items():
            if "regime" in d:
                rows.append((f"  {label}", f"{d['last']} ({d['chg_1']:+.2f}%)", d["regime"]))

    return rows


def main():
    print("=" * 100)
    print("MCX SNAPSHOT — read only")
    print(f"Run at {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 100)

    state, tradable = market_status()
    print(f"\nMCX session status: {state}  (tradable={tradable})")
    if state == "CLOSED":
        print("MCX is closed. Snapshot will use last available data.")

    obj = login()
    if not obj:
        sys.exit(1)
    print("✅ Angel session established")

    import argparse as _ap
_parser = _ap.ArgumentParser()
_parser.add_argument("--product", default="CRUDEOILM",
                     choices=["CRUDEOILM", "GOLDM", "NATGASMINI"])
_args, _ = _parser.parse_known_args()
product = _args.product.upper()

    print("\n" + "─" * 100)
    print(f"PART 1 — CHAIN ({product})")
    print("─" * 100)
    chain = build_chain(obj, product, window_steps=10)
    if chain.get("status") == "OK":
        print_chain(chain)
    else:
        print(f"  chain status: {chain.get('status')}")

    print("\n" + "─" * 100)
    print(f"PART 2 — EXTERNAL CONTEXT ({product})")
    print("─" * 100)
    ctx = fetch_context(product)
    print_context(ctx)

    print("\n" + "─" * 100)
    print("PART 3 — SIGNAL SUMMARY (informational only, no trade decision)")
    print("─" * 100)
    rows = read_summary(chain, ctx)
    if rows:
        print(f"\n  {'Layer':<22} {'Value':<30} {'Read':<45}")
        print("  " + "-" * 97)
        for layer, value, read in rows:
            print(f"  {layer:<22} {value:<30} {read:<45}")
    else:
        print("  No data to summarize.")

    print(f"\n{'=' * 100}")
    print(f"MCX SNAPSHOT COMPLETE. No trades executed. No state written.")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    main()

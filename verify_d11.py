"""Verify _fetch_option_quote_full returns non-zero bid/ask for a real option."""
import sys
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot

b = UnifiedTradingBot("NIFTY")
b.connect_with_retry()
b.load_instruments()

spot = b.get_spot()
expiry = b.get_expiry()
options, atm = b.get_options(spot, expiry)
print(f"spot={spot} atm={atm} expiry={expiry} options={len(options)}")

# Pick the ATM CE
target = None
for o in options:
    if o.get("type") == "CE" and abs(float(o["strike"]) - atm) < 1:
        target = o
        break
if target is None and options:
    target = options[0]

print(f"Target: {target['type']} {target['strike']} token={target['token']} symbol={target['symbol']}")
q = b._fetch_option_quote_full(target["symbol"], target["token"])
print(f"Live FULL quote: {q}")

assert q["ltp"] is not None and q["ltp"] > 0, "ltp missing"
assert q["bid"] is not None and q["bid"] > 0, "bid missing"
assert q["ask"] is not None and q["ask"] > 0, "ask missing"
assert q["ask"] > q["bid"], "crossed book"

# Compute fill using real quote
fill, status = b.capital_engine.compute_paper_fill(q["bid"], q["ask"], q["ltp"], direction="BUY")
print(f"compute_paper_fill: fill={fill} status={status}")
assert status == "OK", f"fill failed: {status}"
print()
print("D11 verification PASSED")

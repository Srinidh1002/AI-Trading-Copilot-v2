"""
Live read-only NIFTY option decision test.

Flow:
1. Fetch NIFTY spot
2. Run full market analysis
3. If NO_TRADE -> stop
4. If TRADE -> build option chain and select contract

No orders are placed.
"""

from pprint import pprint

from services.broker.angel_client import (
    AngelMarketDataClient,
)

from services.live_option_decision_pipeline import (
    LiveOptionDecisionPipeline,
)


NIFTY_TOKEN = "99926000"


print("\n================================")
print("AI TRADING COPILOT")
print("LIVE OPTION DECISION")
print("================================")


# ---------------------------------
# FETCH CURRENT NIFTY SPOT
# ---------------------------------

print("\nFetching NIFTY spot...")

client = AngelMarketDataClient()

response = client.get_market_data(
    mode="LTP",
    exchange_tokens={
        "NSE": [NIFTY_TOKEN]
    },
)

fetched = (
    response
    .get("data", {})
    .get("fetched", [])
)

if not fetched:
    raise RuntimeError(
        "No NIFTY spot data received."
    )

spot_price = float(
    fetched[0].get(
        "ltp",
        0,
    )
    or 0
)

if spot_price <= 0:
    raise RuntimeError(
        "Invalid NIFTY spot price."
    )

print(
    f"NIFTY Spot: {spot_price}"
)


# ---------------------------------
# RUN COMPLETE PIPELINE
# ---------------------------------

print("\nRunning market intelligence pipeline...")

pipeline = LiveOptionDecisionPipeline()

result = pipeline.analyse(
    exchange="NSE",
    symboltoken=NIFTY_TOKEN,
    underlying="NIFTY",
    spot_price=spot_price,
    strikes_each_side=5,
)


# ---------------------------------
# MARKET DECISION
# ---------------------------------

print("\nMARKET DECISION")
print("===============")

print(
    "Market Decision:",
    result["market_decision"],
)

print(
    "Direction:",
    result["direction"],
)

strategy = (
    result["market_analysis"]
    .get("strategy", {})
)

print(
    "Strategy:",
    strategy.get("strategy")
)

print(
    "Confidence:",
    strategy.get("confidence")
)

print(
    "Risk Flags:",
    strategy.get("risk_flags")
)


# ---------------------------------
# FINAL OPTION DECISION
# ---------------------------------

print("\nFINAL OPTION DECISION")
print("=====================")

print(
    "Decision:",
    result["decision"]
)

contract = result["contract"]

print(
    "Contract Selected:",
    contract["selected"]
)


if contract["selected"]:

    print("\nSELECTED CONTRACT")
    print("=================")

    pprint(contract)

else:

    print("\nNO CONTRACT SELECTED")

    for reason in contract.get(
        "reasons",
        [],
    ):
        print(
            "-",
            reason,
        )


# ---------------------------------
# SAFETY STATUS
# ---------------------------------

print("\nSAFETY STATUS")
print("=============")

if result["decision"] == "NO_TRADE":
    print(
        "Market conditions did not pass "
        "the trade authorization gate."
    )

    print(
        "No option contract was selected."
    )

else:
    print(
        "Market analysis authorized a trade "
        "and a contract passed selection filters."
    )


print("\nREAD-ONLY ANALYSIS COMPLETE")
print("NO ORDER WAS PLACED")
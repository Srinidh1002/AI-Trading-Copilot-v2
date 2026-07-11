"""
Live read-only NIFTY option-chain test.

Fetches:
1. Current NIFTY spot price
2. Nearest listed expiry
3. Nearby CE and PE contracts
4. Live FULL market data

No orders are placed.
"""

from services.broker.angel_client import (
    AngelMarketDataClient,
)

from services.live_option_chain_builder import (
    LiveOptionChainBuilder,
)


NIFTY_TOKEN = "99926000"


print("Starting Angel One client...")

client = AngelMarketDataClient()


# ---------------------------------
# FETCH LIVE NIFTY SPOT
# ---------------------------------

print("\nFetching live NIFTY spot price...")

spot_response = client.get_market_data(
    mode="LTP",
    exchange_tokens={
        "NSE": [NIFTY_TOKEN]
    },
)

fetched = (
    spot_response
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
        "Invalid NIFTY spot price received."
    )

print(
    f"NIFTY spot price: {spot_price}"
)


# ---------------------------------
# BUILD LIVE OPTION CHAIN
# ---------------------------------

print(
    "\nBuilding nearby live option chain..."
)

builder = LiveOptionChainBuilder(
    market_client=client
)

result = builder.build_chain(
    underlying="NIFTY",
    spot_price=spot_price,
    strikes_each_side=5,
)


# ---------------------------------
# DISPLAY SUMMARY
# ---------------------------------

print("\nOPTION CHAIN SUMMARY")
print("====================")

print(
    "Underlying:",
    result["underlying"],
)

print(
    "Spot:",
    result["spot_price"],
)

print(
    "Expiry:",
    result["expiry"],
)

print(
    "Contracts requested:",
    result["requested_contracts"],
)

print(
    "Contracts received:",
    result["received_contracts"],
)


# ---------------------------------
# DISPLAY CONTRACTS
# ---------------------------------

print("\nLIVE CONTRACTS")
print("==============")

for contract in sorted(
    result["contracts"],
    key=lambda item: (
        item["strike"],
        item["option_type"],
    ),
):
    print(
        f"{contract['strike']:>8.0f} "
        f"{contract['option_type']} | "
        f"LTP: {contract['premium']:>8.2f} | "
        f"Bid: {contract['bid']:>8.2f} | "
        f"Ask: {contract['ask']:>8.2f} | "
        f"Vol: {contract['volume']:>10} | "
        f"OI: {contract['open_interest']:>10}"
    )


print("\nREAD-ONLY OPTION CHAIN COMPLETE")
print("NO ORDER WAS PLACED")
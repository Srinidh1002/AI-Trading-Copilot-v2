"""
Live read-only test for Angel One Option Greeks.

Automatically discovers the nearest listed NIFTY expiry.
No orders are placed.
"""

from pprint import pprint

from services.angel_instrument_master import (
    AngelInstrumentMaster,
)

from services.broker.angel_client import (
    AngelMarketDataClient,
)


UNDERLYING = "NIFTY"


print("Discovering nearest NIFTY expiry...")

instrument_master = AngelInstrumentMaster()

nearest_expiry = (
    instrument_master.get_nearest_expiry(
        UNDERLYING
    )
)

expiry = nearest_expiry["display"]

print(
    f"Nearest listed expiry: {expiry}"
)


print("\nLogging into Angel One...")

client = AngelMarketDataClient()

client.login()


print(
    f"\nFetching {UNDERLYING} Option Greeks "
    f"for {expiry}..."
)

try:
    response = client.get_option_greeks(
        name=UNDERLYING,
        expiry_date=expiry,
    )

except RuntimeError as error:
    print("\nOPTION GREEKS REQUEST FAILED")
    print("============================")
    print(error)

else:
    print("\nRAW OPTION GREEKS RESPONSE")
    print("==========================")

    pprint(response)

    data = response.get(
        "data",
        [],
    )

    print(
        f"\nContracts received: {len(data)}"
    )

    if data:
        print("\nFIRST CONTRACT")
        print("==============")

        pprint(data[0])
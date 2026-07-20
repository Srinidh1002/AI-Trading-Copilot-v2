from services.angel_instrument_master import (
    AngelInstrumentMaster,
)


print(
    "Downloading Angel One instrument master..."
)

service = AngelInstrumentMaster()

contracts = service.get_option_contracts(
    "NIFTY"
)

print(
    f"\nNIFTY option contracts found: "
    f"{len(contracts)}"
)

expiries = service.get_available_expiries(
    "NIFTY"
)

print("\nAVAILABLE NIFTY EXPIRIES")
print("========================")

for index, expiry in enumerate(
    expiries,
    start=1,
):
    print(
        f"{index}. "
        f"{expiry['display']} "
        f"(raw: {expiry['raw']})"
    )

if expiries:
    nearest = expiries[0]

    print("\nNEAREST EXPIRY")
    print("==============")

    print(
        nearest["display"]
    )
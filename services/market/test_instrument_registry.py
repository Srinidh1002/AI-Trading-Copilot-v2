from pprint import pprint

from services.market.instrument_registry import InstrumentMaster


def main():

    registry = InstrumentMaster()

    registry.load()

    print("\n")
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    pprint(
        registry.summary()
    )

    print("\n")
    print("=" * 70)
    print("UNDERLYINGS")
    print("=" * 70)

    pprint(
        registry.underlyings()
    )

    print("\n")
    print("=" * 70)
    print("NIFTY EXPIRIES")
    print("=" * 70)

    pprint(
        registry.expiries(
            "NIFTY"
        )[:5]
    )

    expiry = registry.nearest_expiry(
        "NIFTY"
    )

    print("\nNearest Expiry :", expiry)

    print("\nATM Strike :", registry.atm(
        "NIFTY",
        expiry,
        24334.3,
    ))

    print("\n")
    print("=" * 70)
    print("TOKEN LOOKUP")
    print("=" * 70)

    contract = registry.get_by_token(
        "65852"
    )

    pprint(contract)


if __name__ == "__main__":
    main()
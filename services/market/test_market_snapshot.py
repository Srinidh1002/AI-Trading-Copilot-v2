from pprint import pprint

from services.market.market_snapshot import MarketSnapshot


def main():

    market = MarketSnapshot()

    snapshot = market.snapshot(
        "NIFTY",
        levels=2,
    )

    print("\n")
    print("=" * 70)
    print("INDEX")
    print("=" * 70)

    pprint(snapshot["index"])

    print("\n")
    print("=" * 70)
    print("OPTION FETCHED")
    print("=" * 70)

    pprint(
        snapshot["options"]["quotes"]["data"]["fetched"][:2]
    )


if __name__ == "__main__":
    main()
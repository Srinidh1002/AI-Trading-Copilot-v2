from pprint import pprint

from services.market.live_index_price import LiveIndexPrice
from services.market.option_market import OptionMarket


def main():

    index = LiveIndexPrice()

    option = OptionMarket()

    spot = index.get_price("NIFTY")["LTP"]

    print("\n")
    print("=" * 70)
    print("ATM CONTRACT")
    print("=" * 70)

    pprint(
        option.contracts(
            "NIFTY",
            spot,
        )
    )

    print("\n")
    print("=" * 70)
    print("ATM LIVE QUOTES")
    print("=" * 70)

    pprint(
        option.live_quotes(
            "NIFTY",
            spot,
        )
    )

    print("\n")
    print("=" * 70)
    print("CHAIN QUOTES")
    print("=" * 70)

    data = option.chain_quotes(
        "NIFTY",
        spot,
        levels=2,
    )

    pprint(data["quotes"])


if __name__ == "__main__":
    main()
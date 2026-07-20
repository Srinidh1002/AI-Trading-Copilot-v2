"""
Test - Live Market Service
"""

from pprint import pprint

from services.market.live_market import LiveMarket


def main():

    market = LiveMarket()

    print("\n")
    print("=" * 70)
    print("LIVE NIFTY LTP")
    print("=" * 70)

    data = market.get_ltp(
        exchange="NSE",
        symbol="NIFTY",
        token="99926000",
    )

    pprint(data)

    print("\n")
    print("=" * 70)
    print("LIVE NIFTY OHLC")
    print("=" * 70)

    data = market.get_ohlc(
        exchange="NSE",
        tokens=["99926000"],
    )

    pprint(data)

    print("\n")
    print("=" * 70)
    print("LIVE NIFTY FULL")
    print("=" * 70)

    data = market.get_full(
        exchange="NSE",
        tokens=["99926000"],
    )

    pprint(data)

    print("\n")
    print("=" * 70)
    print("MULTIPLE LTP")
    print("=" * 70)

    data = market.get_multiple_ltp(
        exchange="NSE",
        tokens=[
            "99926000",  # NIFTY
            "99926009",  # BANKNIFTY
        ],
    )

    pprint(data)


if __name__ == "__main__":
    main()
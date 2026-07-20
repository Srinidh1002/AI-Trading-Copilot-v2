"""
SmartAPI Client Test
"""

from pprint import pprint

from services.broker.smart_api_client import SmartAPIClient


def main():

    client = SmartAPIClient()

    print("\n")
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    pprint(client.summary())

    print("\n")
    print("=" * 70)
    print("PROFILE")
    print("=" * 70)

    pprint(client.get_profile())

    print("\n")
    print("=" * 70)
    print("HOLDINGS")
    print("=" * 70)

    try:
        pprint(client.holdings())
    except Exception as e:
        print(e)

    print("\n")
    print("=" * 70)
    print("POSITIONS")
    print("=" * 70)

    try:
        pprint(client.positions())
    except Exception as e:
        print(e)

    print("\n")
    print("=" * 70)
    print("ORDER BOOK")
    print("=" * 70)

    try:
        pprint(client.order_book())
    except Exception as e:
        print(e)

    print("\n")
    print("=" * 70)
    print("TRADE BOOK")
    print("=" * 70)

    try:
        pprint(client.trade_book())
    except Exception as e:
        print(e)

    print("\n")
    print("=" * 70)
    print("LIVE NIFTY")
    print("=" * 70)

    try:

        pprint(
            client.ltp(
                "NSE",
                "NIFTY",
                "99926000",
            )
        )

    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()
from pprint import pprint

from services.market.live_index_price import LiveIndexPrice


def main():

    engine = LiveIndexPrice()

    print("\n")
    print("=" * 70)
    print("NIFTY")
    print("=" * 70)

    pprint(engine.get_price("NIFTY"))

    print("\n")
    print("=" * 70)
    print("BANKNIFTY")
    print("=" * 70)

    pprint(engine.get_price("BANKNIFTY"))

    print("\n")
    print("=" * 70)
    print("SENSEX")
    print("=" * 70)

    pprint(engine.get_price("SENSEX"))

    print("\n")
    print("=" * 70)
    print("ALL INDICES")
    print("=" * 70)

    pprint(engine.get_all_prices())


if __name__ == "__main__":
    main()
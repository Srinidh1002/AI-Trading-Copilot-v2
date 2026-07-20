from services.market.historical_market import HistoricalMarket


def main():

    market = HistoricalMarket()

    df = market.get_data(

        exchange="NSE",

        token="99926000",

        interval="ONE_DAY",

        from_date="2026-06-01 09:15",

        to_date="2026-07-18 15:30",

    )

    print("\n")
    print("=" * 70)
    print("HISTORICAL DATA")
    print("=" * 70)

    print(df.head())

    print("\nRows :", len(df))

    print("\nColumns :")

    print(df.columns.tolist())


if __name__ == "__main__":
    main()
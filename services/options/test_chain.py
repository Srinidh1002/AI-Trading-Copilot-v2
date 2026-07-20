from services.market.option_market import OptionMarket

market = OptionMarket()

quotes = market.chain_quotes(

    "NIFTY",

    24346.7,

    levels=3,

)

print(

    len(
        quotes["data"]["fetched"]
    )

)

for item in quotes["data"]["fetched"]:

    print(

        item["tradingSymbol"],

        item["ltp"],

        item["opnInterest"]

    )
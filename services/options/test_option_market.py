from services.market.option_market import OptionMarket

market = OptionMarket()

spot = 24346.7

contracts = market.contracts(
    "NIFTY",
    spot,
)

print("\nExpiry")
print(contracts["expiry"])

print("\nATM")
print(contracts["strike"])

print("\nCE")
print(contracts["CE"]["symbol"])

print("\nPE")
print(contracts["PE"]["symbol"])

print("\nFetching Live Quotes...")

quotes = market.live_quotes(
    "NIFTY",
    spot,
)

print(quotes)
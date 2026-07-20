from services.market.option_market import OptionMarket
from services.options.oi_engine import OIEngine

market = OptionMarket()

quotes = market.live_quotes(
    "NIFTY",
    24346.7,
)

result = OIEngine.analyze(
    quotes
)

print(result)
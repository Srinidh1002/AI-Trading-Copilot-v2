from pprint import pprint

from services.market.option_market import OptionMarket
from services.options.max_pain_engine import MaxPainEngine

market = OptionMarket()

chain = market.chain_quotes(
    "NIFTY",
    24346.7,
    levels=10,
)

result = MaxPainEngine.analyze(chain)

pprint(result)
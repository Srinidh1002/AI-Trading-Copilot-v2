from pprint import pprint

from services.market.option_market import OptionMarket
from services.decision.decision_engine import DecisionEngine

market = OptionMarket()

chain = market.chain_quotes(
    "NIFTY",
    24346.7,
    levels=10,
)

result = DecisionEngine.analyze(chain)

pprint(result)
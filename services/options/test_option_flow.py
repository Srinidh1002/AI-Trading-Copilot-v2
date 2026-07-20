from pprint import pprint

from services.market.option_market import OptionMarket
from services.options.option_flow_engine import OptionFlowEngine

market = OptionMarket()

chain = market.chain_quotes(
    "NIFTY",
    24346.7,
    levels=10,
)

result = OptionFlowEngine.analyze(chain)

pprint(result)
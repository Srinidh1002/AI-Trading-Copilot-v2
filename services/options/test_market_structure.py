from pprint import pprint

from services.market.option_market import OptionMarket
from services.options.option_flow_engine import OptionFlowEngine
from services.options.market_structure_engine import MarketStructureEngine

market = OptionMarket()

chain = market.chain_quotes(
    "NIFTY",
    24346.7,
    levels=10,
)

flow = OptionFlowEngine.analyze(chain)

result = MarketStructureEngine.analyze(flow)

pprint(result)
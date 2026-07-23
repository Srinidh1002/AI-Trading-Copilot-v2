"""
Market Snapshot

Provides a unified market snapshot
for the Decision Engine and AI Engine.
"""

from services.market.live_index_price import LiveIndexPrice
from services.market.option_market import OptionMarket
from services.options.option_chain_engine import OptionChainEngine


class MarketSnapshot:

    def __init__(self):

        self.index = LiveIndexPrice()

        self.option = OptionMarket()

        

    # -----------------------------------------------------

    def snapshot(
        self,
        underlying="NIFTY",
        expiry=None,
        levels=5,
    ):

        index_data = self.index.get_price(
            underlying
        )

        option_chain = self.option.chain_quotes(
            underlying,
            index_data["LTP"],
            levels,
        )

        option_analysis = {}

        if expiry is not None:

            try:

                option_analysis = self.option.analyze(
                    underlying,
                    index_data["LTP"],
                )

            except Exception as e:

                import traceback

                traceback.print_exc()

                option_analysis = {
                    "Status": "Error",
                    "Error": str(e),
                }

        return {

            "index": index_data,

            "options": option_chain,

            "option_analysis": option_analysis,

        }
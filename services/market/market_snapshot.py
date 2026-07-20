"""
Market Snapshot

Provides a single snapshot of the market
for the AI Engine.
"""

from services.market.live_index_price import LiveIndexPrice
from services.market.option_market import OptionMarket


class MarketSnapshot:

    def __init__(self):

        self.index = LiveIndexPrice()

        self.option = OptionMarket()

    # -----------------------------------------------------

    def snapshot(
        self,
        underlying="NIFTY",
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

        return {

            "index": index_data,

            "options": option_chain,

        }
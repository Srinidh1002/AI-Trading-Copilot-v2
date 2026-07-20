"""
Live Index Price Engine

Uses the centralized Broker Session Manager.
"""

from services.broker.session_manager import SessionManager


class LiveIndexPrice:

    def __init__(self):

        self.session = SessionManager()

        self.indices = {

            "NIFTY": {
                "exchange": "NSE",
                "symbol": "NIFTY",
                "token": "99926000",
            },

            "BANKNIFTY": {
                "exchange": "NSE",
                "symbol": "BANKNIFTY",
                "token": "99926009",
            },

            "SENSEX": {
                "exchange": "BSE",
                "symbol": "SENSEX",
                "token": "99919000",
            },

        }

    # -----------------------------------------------------

    def get_price(
        self,
        symbol="NIFTY",
    ):

        if symbol not in self.indices:

            raise ValueError(
                f"Unsupported Index : {symbol}"
            )

        index = self.indices[symbol]

        data = self.session.execute(

            self.session.client.ltp,

            index["exchange"],

            index["symbol"],

            index["token"],

        )

        return {

            "Symbol": symbol,

            "Exchange": index["exchange"],

            "Token": index["token"],

            "LTP": float(data["ltp"]),

            "Open": float(data["open"]),

            "High": float(data["high"]),

            "Low": float(data["low"]),

            "Close": float(data["close"]),

        }

    # -----------------------------------------------------

    def get_all_prices(self):

        prices = {}

        for symbol in self.indices:

            prices[symbol] = self.get_price(symbol)

        return prices
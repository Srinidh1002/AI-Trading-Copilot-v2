"""
Live Market Service

Provides live market data through the centralized
Broker Session Manager.
"""

from services.broker.session_manager import SessionManager


class LiveMarket:

    def __init__(self):

        self.session = SessionManager()

    # -----------------------------------------------------

    def get_ltp(
        self,
        exchange: str,
        symbol: str,
        token: str,
    ):

        return self.session.execute(
            self.session.client.ltp,
            exchange,
            symbol,
            token,
        )

    # -----------------------------------------------------

    def get_ohlc(
        self,
        exchange: str,
        tokens: list[str],
    ):

        return self.session.execute(
            self.session.api.getMarketData,
            "OHLC",
            {
                exchange: tokens
            },
        )

    # -----------------------------------------------------

    def get_full(
        self,
        exchange: str,
        tokens: list[str],
    ):

        return self.session.execute(
            self.session.api.getMarketData,
            "FULL",
            {
                exchange: tokens
            },
        )

    # -----------------------------------------------------

    def get_multiple_ltp(
        self,
        exchange: str,
        tokens: list[str],
    ):

        return self.session.execute(
            self.session.api.getMarketData,
            "LTP",
            {
                exchange: tokens
            },
        )
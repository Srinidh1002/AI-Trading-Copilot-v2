"""
Angel Option Client

Handles:
- PCR
- Option Greeks

Uses existing authenticated AngelMarketDataClient.
"""

from services.broker.angel_client import AngelMarketDataClient


class AngelOptionClient:

    def __init__(self):
        self.client = AngelMarketDataClient()

    def get_pcr(self):
        """
        Placeholder.

        Next step:
        Call Angel REST PCR endpoint using the
        authenticated session.
        """
        raise NotImplementedError

    def get_option_greeks(
        self,
        underlying,
        expiry,
    ):
        """
        Returns Greeks from SmartAPI.
        """

        return self.client.get_option_greeks(
            underlying,
            expiry,
        )
"""
Angel Option Client

Provides:
- Live Option Chain
- PCR
- Option Greeks

Uses the shared authenticated AngelMarketDataClient.
"""

from services.broker.shared_client import get_market_client
from services.market.instrument_registry import InstrumentMaster


class AngelOptionClient:

    # Number of strikes on each side of ATM
    STRIKE_WINDOW = 10

    def __init__(self):

        # Use the shared market client
        self.client = get_market_client()

        self.registry = InstrumentMaster()

        self.registry.load()

    # -----------------------------------------------------

    def get_option_chain(
        self,
        underlying,
        expiry,
        spot,
    ):
        """
        Returns a live option chain around ATM.

        Only a limited strike window is requested to stay
        within Angel One token limits.
        """

        chain = self.registry.option_chain(
            underlying,
            expiry,
        )

        strikes = self.registry.strikes(
            underlying,
            expiry,
        )

        atm = self.registry.atm(
            underlying,
            expiry,
            spot,
        )

        if atm is None:
            return []

        index = strikes.index(atm)

        selected = strikes[
            max(0, index - self.STRIKE_WINDOW):
            min(
                len(strikes),
                index + self.STRIKE_WINDOW + 1,
            )
        ]

        ce_map = {
            x["strike"]: x
            for x in chain["CE"]
        }

        pe_map = {
            x["strike"]: x
            for x in chain["PE"]
        }

        tokens = []

        token_to_strike = {}

        for strike in selected:

            ce = ce_map.get(strike)

            if ce:

                token = str(ce["token"])

                tokens.append(token)

                token_to_strike[token] = strike

            pe = pe_map.get(strike)

            if pe:

                token = str(pe["token"])

                tokens.append(token)

                token_to_strike[token] = strike

        quotes = self.client.get_option_chain(
            {
                "NFO": tokens,
            }
        )

        fetched = (
            quotes.get("data", {})
            .get("fetched", [])
        )

        for option in fetched:

            strike = token_to_strike.get(
                str(option["symbolToken"])
            )

            if strike is not None:

                option["strikePrice"] = strike

        return fetched

    # -----------------------------------------------------

    def get_pcr(
        self,
        underlying,
        expiry,
        spot,
    ):
        """
        Calculate PCR from the live option chain.
        """

        chain = self.get_option_chain(
            underlying,
            expiry,
            spot,
        )

        call_oi = 0
        put_oi = 0

        for option in chain:

            symbol = option.get(
                "tradingSymbol",
                "",
            )

            oi = float(
                option.get(
                    "opnInterest",
                    0,
                )
            )

            if symbol.endswith("CE"):

                call_oi += oi

            elif symbol.endswith("PE"):

                put_oi += oi

        pcr = round(
            put_oi / call_oi,
            2,
        ) if call_oi else 0.0

        return {

            "PCR": pcr,

            "CallOI": int(call_oi),

            "PutOI": int(put_oi),

        }

    # -----------------------------------------------------

    def get_option_greeks(
        self,
        underlying,
        expiry,
    ):

        return self.client.get_option_greeks(
            underlying,
            expiry,
        )
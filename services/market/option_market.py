"""
Option Market Service

Uses the centralized Broker Session Manager.
"""

from services.broker.session_manager import SessionManager
from services.market.instrument_registry import InstrumentMaster


class OptionMarket:

    def __init__(self):

        self.session = SessionManager()

        self.registry = InstrumentMaster()

        self.registry.load()

    # -------------------------------------------------

    def current_expiry(
        self,
        underlying,
    ):

        return self.registry.nearest_expiry(
            underlying
        )

    # -------------------------------------------------

    def atm_strike(
        self,
        underlying,
        spot,
    ):

        expiry = self.current_expiry(
            underlying
        )

        return self.registry.atm(
            underlying,
            expiry,
            spot,
        )

    # -------------------------------------------------

    def contracts(
        self,
        underlying,
        spot,
    ):

        expiry = self.current_expiry(
            underlying,
        )

        strike = self.registry.atm(
            underlying,
            expiry,
            spot,
        )

        chain = self.registry.option_chain(
            underlying,
            expiry,
        )

        ce = next(
            x
            for x in chain["CE"]
            if x["strike"] == strike
        )

        pe = next(
            x
            for x in chain["PE"]
            if x["strike"] == strike
        )

        return {

            "expiry": expiry,

            "strike": strike,

            "CE": ce,

            "PE": pe,

        }

    # -------------------------------------------------

    def live_quotes(
        self,
        underlying,
        spot,
    ):

        contracts = self.contracts(
            underlying,
            spot,
        )

        tokens = [

            contracts["CE"]["token"],

            contracts["PE"]["token"],

        ]

        return self.session.execute(

            self.session.api.getMarketData,

            "FULL",

            {
                "NFO": tokens,
            },

        )

    # -------------------------------------------------

    def chain_quotes(
        self,
        underlying,
        spot,
        levels=5,
    ):

        expiry = self.current_expiry(
            underlying,
        )

        atm = self.registry.atm(
            underlying,
            expiry,
            spot,
        )

        strikes = self.registry.strikes(
            underlying,
            expiry,
        )

        index = strikes.index(atm)

        selected = strikes[
            max(0, index - levels):
            min(len(strikes), index + levels + 1)
        ]

        chain = self.registry.option_chain(
            underlying,
            expiry,
        )

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

            pe = pe_map.get(strike)

            if ce:

                tokens.append(
                    ce["token"]
                )

                token_to_strike[
                    ce["token"]
                ] = strike

            if pe:

                tokens.append(
                    pe["token"]
                )

                token_to_strike[
                    pe["token"]
                ] = strike

        quotes = self.session.execute(

            self.session.api.getMarketData,

            "FULL",

            {
                "NFO": tokens,
            },

        )

        return {

            "quotes": quotes,

            "token_to_strike": token_to_strike,

        }
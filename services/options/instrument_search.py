"""
Instrument Search Engine

Searches option contracts from the instrument master.
"""

from services.market.instrument_registry import InstrumentMaster


class InstrumentSearch:

    def __init__(self):

        self.master = InstrumentMaster()
        self.master.load()

    def get_expiries(self, underlying):

        return self.master.expiries(underlying)

    def get_nearest_expiry(self, underlying):

        expiries = self.master.expiries(underlying)

        if not expiries:
            return None

        return expiries[0]

    def get_option_chain(
        self,
        underlying,
        expiry,
    ):

        contracts = self.master.contracts(
            underlying,
            expiry,
        )

        calls = []
        puts = []

        for contract in contracts:

            symbol = contract.get("symbol", "")

            if symbol.endswith("CE"):
                calls.append(contract)

            elif symbol.endswith("PE"):
                puts.append(contract)

        calls = sorted(
            calls,
            key=lambda x: float(x["strike"])
        )

        puts = sorted(
            puts,
            key=lambda x: float(x["strike"])
        )

        return {
            "calls": calls,
            "puts": puts,
        }

    def get_atm(self, underlying, expiry, ltp):

        chain = self.get_option_chain(
            underlying,
            expiry,
        )

        strikes = sorted(
            {
                float(c["strike"])
                for c in chain["calls"]
            }
        )

        atm = min(
            strikes,
            key=lambda s: abs(s - ltp)
        )

        return atm
    
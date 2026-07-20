"""
Instrument Registry

Production registry for Angel One Index Option contracts.
"""

import json
from collections import defaultdict
from pathlib import Path


CACHE = Path("data/instruments.json")

SUPPORTED = {
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "SENSEX",
}


class InstrumentMaster:

    def __init__(self):

        self.registry = defaultdict(
            lambda: defaultdict(
                lambda: {
                    "CE": [],
                    "PE": [],
                }
            )
        )

        self.by_symbol = {}

        self.by_token = {}

        self.loaded = False

    # -----------------------------------------------------

    def load(self):

        if self.loaded:
            return

        if not CACHE.exists():

            raise FileNotFoundError(
                "Run download_master.py first."
            )

        with open(
            CACHE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        for contract in data:

            if contract.get("instrumenttype") != "OPTIDX":
                continue

            if contract.get("exch_seg") != "NFO":
                continue

            underlying = contract.get(
                "name",
                "",
            ).upper()

            if underlying not in SUPPORTED:
                continue

            symbol = contract.get(
                "symbol",
                "",
            )

            if symbol.endswith("CE"):
                option_type = "CE"

            elif symbol.endswith("PE"):
                option_type = "PE"

            else:
                continue

            expiry = contract["expiry"]

            strike = (
                float(contract["strike"]) / 100
            )

            contract["strike"] = strike

            self.registry[
                underlying
            ][
                expiry
            ][
                option_type
            ].append(contract)

            self.by_symbol[
                symbol
            ] = contract

            self.by_token[
                contract["token"]
            ] = contract

        for underlying in self.registry.values():

            for expiry in underlying.values():

                expiry["CE"].sort(
                    key=lambda x: x["strike"]
                )

                expiry["PE"].sort(
                    key=lambda x: x["strike"]
                )

        self.loaded = True

    # -----------------------------------------------------

    def underlyings(self):

        return sorted(
            self.registry.keys()
        )

    # -----------------------------------------------------

    def expiries(
        self,
        underlying,
    ):

        return sorted(
            self.registry[
                underlying
            ].keys()
        )

    # -----------------------------------------------------

    def nearest_expiry(
        self,
        underlying,
    ):

        expiries = self.expiries(
            underlying
        )

        if not expiries:
            return None

        return expiries[0]

    # -----------------------------------------------------

    def option_chain(
        self,
        underlying,
        expiry,
    ):

        return self.registry[
            underlying
        ][
            expiry
        ]

    # -----------------------------------------------------

    def strikes(
        self,
        underlying,
        expiry,
    ):

        return [

            x["strike"]

            for x in self.registry[
                underlying
            ][
                expiry
            ]["CE"]

        ]

    # -----------------------------------------------------

    def atm(
        self,
        underlying,
        expiry,
        ltp,
    ):

        strikes = self.strikes(
            underlying,
            expiry,
        )

        if not strikes:
            return None

        return min(
            strikes,
            key=lambda strike: abs(
                strike - ltp
            ),
        )

    # -----------------------------------------------------

    def get_by_symbol(
        self,
        symbol,
    ):

        return self.by_symbol.get(
            symbol
        )

    # -----------------------------------------------------

    def get_by_token(
        self,
        token,
    ):

        return self.by_token.get(
            str(token)
        )

    # -----------------------------------------------------

    def token(
        self,
        symbol,
    ):

        contract = self.get_by_symbol(
            symbol
        )

        if contract:
            return contract["token"]

        return None

    # -----------------------------------------------------

    def summary(self):

        return {

            "Underlyings": self.underlyings(),

            "Contracts": len(
                self.by_token
            ),

        }
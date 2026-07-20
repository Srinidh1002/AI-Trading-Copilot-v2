"""
Option Flow Engine

Analyzes the complete option chain.
"""


class OptionFlowEngine:

    @staticmethod
    def analyze(option_chain):

        fetched = option_chain["quotes"]["data"]["fetched"]
        token_map = option_chain["token_to_strike"]

        strikes = {}

        total_ce = 0
        total_pe = 0

        for option in fetched:

            strike = token_map.get(option["symbolToken"])

            if strike is None:
                continue

            if strike not in strikes:

                strikes[strike] = {
                    "CE": None,
                    "PE": None,
                }

            if option["tradingSymbol"].endswith("CE"):

                strikes[strike]["CE"] = option
                total_ce += option["opnInterest"]

            else:

                strikes[strike]["PE"] = option
                total_pe += option["opnInterest"]

        pcr = round(
            total_pe / total_ce,
            2,
        ) if total_ce else 0

        support = max(

            strikes.items(),

            key=lambda x:
            x[1]["PE"]["opnInterest"]
            if x[1]["PE"] else 0,

        )[0]

        resistance = max(

            strikes.items(),

            key=lambda x:
            x[1]["CE"]["opnInterest"]
            if x[1]["CE"] else 0,

        )[0]

        strongest_put = strikes[support]["PE"]

        strongest_call = strikes[resistance]["CE"]

        return {

            "PCR": pcr,

            "TotalCEOI": total_ce,

            "TotalPEOI": total_pe,

            "Support": support,

            "Resistance": resistance,

            "StrongestCall": strongest_call,

            "StrongestPut": strongest_put,

            "Chain": strikes,

        }
    
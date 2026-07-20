"""
Max Pain Engine
"""

class MaxPainEngine:

    @staticmethod
    def analyze(option_chain):

        fetched = option_chain["quotes"]["data"]["fetched"]
        token_map = option_chain["token_to_strike"]

        strikes = {}

        for option in fetched:

            strike = token_map.get(option["symbolToken"])

            if strike is None:
                continue

            if strike not in strikes:

                strikes[strike] = {
                    "CE_OI": 0,
                    "PE_OI": 0,
                }

            if option["tradingSymbol"].endswith("CE"):

                strikes[strike]["CE_OI"] = option["opnInterest"]

            else:

                strikes[strike]["PE_OI"] = option["opnInterest"]

        support = max(
            strikes.items(),
            key=lambda x: x[1]["PE_OI"],
        )[0]

        resistance = max(
            strikes.items(),
            key=lambda x: x[1]["CE_OI"],
        )[0]

        max_pain = min(
            strikes.items(),
            key=lambda x: abs(
                x[1]["CE_OI"] - x[1]["PE_OI"]
            ),
        )[0]

        total_ce = sum(
            x["CE_OI"]
            for x in strikes.values()
        )

        total_pe = sum(
            x["PE_OI"]
            for x in strikes.values()
        )

        pcr = round(
            total_pe / total_ce,
            2,
        ) if total_ce else 0

        return {

            "Support": support,

            "Resistance": resistance,

            "MaxPain": max_pain,

            "PCR": pcr,

            "Total_CE_OI": total_ce,

            "Total_PE_OI": total_pe,

            "Strikes": dict(sorted(strikes.items())),

        }
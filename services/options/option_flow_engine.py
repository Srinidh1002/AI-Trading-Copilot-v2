"""
Production Option Flow Engine

Analyzes institutional option flow using:
- PCR
- Support / Resistance
- Max Pain
- OI Concentration
- Institutional Bias
- Confidence
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

            strike = token_map.get(
                option["symbolToken"]
            )

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

        if not strikes:

            return {

                "PCR": 0,

                "Bias": "Neutral",

                "Confidence": 0,

                "Support": None,

                "Resistance": None,

                "MaxPain": None,

                "Flow": "Unavailable",

                "TotalCEOI": 0,

                "TotalPEOI": 0,

                "StrongestCall": None,

                "StrongestPut": None,

                "Chain": {},

            }

        pcr = round(
            total_pe / total_ce,
            2,
        ) if total_ce else 0

        support = max(

            strikes.items(),

            key=lambda x: (
                x[1]["PE"]["opnInterest"]
                if x[1]["PE"] else 0
            ),

        )[0]

        resistance = max(

            strikes.items(),

            key=lambda x: (
                x[1]["CE"]["opnInterest"]
                if x[1]["CE"] else 0
            ),

        )[0]

        strongest_put = strikes[support]["PE"]

        strongest_call = strikes[resistance]["CE"]

        max_pain = min(

            strikes.items(),

            key=lambda x: abs(

                (
                    x[1]["CE"]["opnInterest"]
                    if x[1]["CE"] else 0
                )

                -

                (
                    x[1]["PE"]["opnInterest"]
                    if x[1]["PE"] else 0
                )

            ),

        )[0]

        if pcr >= 1.30:

            bias = "Strong Bullish"

            confidence = 90

            flow = "Aggressive Put Writing"

        elif pcr >= 1.05:

            bias = "Bullish"

            confidence = 75

            flow = "Put Writing"

        elif pcr <= 0.70:

            bias = "Strong Bearish"

            confidence = 90

            flow = "Aggressive Call Writing"

        elif pcr <= 0.95:

            bias = "Bearish"

            confidence = 75

            flow = "Call Writing"

        else:

            bias = "Neutral"

            confidence = 50

            flow = "Balanced"

        return {

            "PCR": pcr,

            "Bias": bias,

            "Confidence": confidence,

            "Flow": flow,

            "Support": support,

            "Resistance": resistance,

            "MaxPain": max_pain,

            "TotalCEOI": total_ce,

            "TotalPEOI": total_pe,

            "StrongestCall": strongest_call,

            "StrongestPut": strongest_put,

            "Chain": strikes,

        }
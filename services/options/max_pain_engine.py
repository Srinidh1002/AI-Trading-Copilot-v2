"""
Max Pain Engine
"""


class MaxPainEngine:

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
                    "CE_OI": 0,
                    "PE_OI": 0,
                }

            oi = float(option.get("opnInterest", 0))

            if option["tradingSymbol"].endswith("CE"):

                strikes[strike]["CE_OI"] = oi
                total_ce += oi

            else:

                strikes[strike]["PE_OI"] = oi
                total_pe += oi

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

        pcr = round(
            total_pe / total_ce,
            2,
        ) if total_ce else 0.0

        if pcr >= 1.20:
            bias = "Bullish"

        elif pcr <= 0.80:
            bias = "Bearish"

        else:
            bias = "Neutral"

        confidence = round(
            min(
                100,
                50 + abs(total_pe - total_ce) /
                max(total_pe + total_ce, 1) * 100,
            ),
            2,
        )

        return {

            "Support": support,

            "Resistance": resistance,

            "MaxPain": max_pain,

            "PCR": pcr,

            "Bias": bias,

            "Confidence": confidence,

            "Total_CE_OI": int(total_ce),

            "Total_PE_OI": int(total_pe),

            "Strikes": dict(sorted(strikes.items())),
        }
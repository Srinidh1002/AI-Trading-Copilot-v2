"""
Open Interest Engine
"""

class OIEngine:

    @staticmethod
    def analyze(option_data):

        fetched = option_data["data"]["fetched"]

        ce = next(
            x for x in fetched
            if x["tradingSymbol"].endswith("CE")
        )

        pe = next(
            x for x in fetched
            if x["tradingSymbol"].endswith("PE")
        )

        ce_oi = ce["opnInterest"]
        pe_oi = pe["opnInterest"]

        pcr = round(pe_oi / ce_oi, 2) if ce_oi else 0

        if pcr > 1.2:
            bias = "Bullish"

        elif pcr < 0.8:
            bias = "Bearish"

        else:
            bias = "Neutral"

        return {

            "CE_OI": ce_oi,

            "PE_OI": pe_oi,

            "PCR": pcr,

            "Bias": bias,

            "CE": ce,

            "PE": pe,

        }
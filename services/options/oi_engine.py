"""
Open Interest Engine
"""


class OIEngine:

    @staticmethod
    def analyze(option_data):
        """
        Analyze Open Interest across the entire option chain.
        """

        fetched = option_data["data"]["fetched"]

        ce_total_oi = 0
        pe_total_oi = 0

        ce_max_oi = 0
        pe_max_oi = 0

        ce_max_strike = None
        pe_max_strike = None

        ce_max_change = 0
        pe_max_change = 0

        bullish = 0
        bearish = 0

        for option in fetched:

            symbol = option.get("tradingSymbol", "")

            oi = float(option.get("opnInterest", 0))
            oi_change = float(option.get("changeinOpenInterest", 0))
            strike = option.get("strikePrice")

            if symbol.endswith("CE"):

                ce_total_oi += oi

                if oi > ce_max_oi:
                    ce_max_oi = oi
                    ce_max_strike = strike

                if oi_change > ce_max_change:
                    ce_max_change = oi_change

            elif symbol.endswith("PE"):

                pe_total_oi += oi

                if oi > pe_max_oi:
                    pe_max_oi = oi
                    pe_max_strike = strike

                if oi_change > pe_max_change:
                    pe_max_change = oi_change

        pcr = round(
            pe_total_oi / ce_total_oi,
            2,
        ) if ce_total_oi else 0.0

        if pcr >= 1.20:
            bias = "Bullish"
            bullish += 2

        elif pcr <= 0.80:
            bias = "Bearish"
            bearish += 2

        else:
            bias = "Neutral"

        if pe_max_oi > ce_max_oi:
            bullish += 1

        elif ce_max_oi > pe_max_oi:
            bearish += 1

        confidence = min(
            100,
            50 + abs(pe_total_oi - ce_total_oi) / max(pe_total_oi + ce_total_oi, 1) * 100,
        )

        return {

            "CE_OI": int(ce_total_oi),

            "PE_OI": int(pe_total_oi),

            "PCR": pcr,

            "Bias": bias,

            "BullScore": bullish,

            "BearScore": bearish,

            "Confidence": round(confidence, 2),

            "MaxCallOI": int(ce_max_oi),

            "MaxPutOI": int(pe_max_oi),

            "CallResistance": ce_max_strike,

            "PutSupport": pe_max_strike,

            "CallOIChange": int(ce_max_change),

            "PutOIChange": int(pe_max_change),

        }
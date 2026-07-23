"""
PCR Engine

Calculates Put Call Ratio using Option Chain data.
"""


class PCREngine:

    @staticmethod
    def analyze(option_data):

        fetched = option_data["data"]["fetched"]

        call_oi = 0
        put_oi = 0

        max_call_oi = 0
        max_put_oi = 0

        call_resistance = None
        put_support = None

        for option in fetched:

            symbol = option.get("tradingSymbol", "")

            oi = float(option.get("opnInterest", 0))

            strike = option.get("strikePrice")

            if symbol.endswith("CE"):

                call_oi += oi

                if oi > max_call_oi:
                    max_call_oi = oi
                    call_resistance = strike

            elif symbol.endswith("PE"):

                put_oi += oi

                if oi > max_put_oi:
                    max_put_oi = oi
                    put_support = strike

        pcr = round(
            put_oi / call_oi,
            2,
        ) if call_oi else 0.0

        if pcr >= 1.30:
            bias = "Strong Bullish"
            score = 90

        elif pcr >= 1.05:
            bias = "Bullish"
            score = 75

        elif pcr <= 0.70:
            bias = "Strong Bearish"
            score = 10

        elif pcr <= 0.95:
            bias = "Bearish"
            score = 30

        else:
            bias = "Neutral"
            score = 50

        return {

            "PCR": pcr,

            "Bias": bias,

            "Score": score,

            "Confidence": score,

            "CallOI": int(call_oi),

            "PutOI": int(put_oi),

            "CallResistance": call_resistance,

            "PutSupport": put_support,

            "Reason": f"PCR = {pcr} ({bias})",
        }
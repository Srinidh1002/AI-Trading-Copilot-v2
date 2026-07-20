"""
Smart Money Engine

Converts strike-wise OI states into a market-wide view.
"""


class SmartMoneyEngine:

    @staticmethod
    def analyze(option_flow, oi_changes):

        bullish = 0
        bearish = 0

        observations = []

        support = option_flow["Support"]
        resistance = option_flow["Resistance"]

        for strike, change in oi_changes.items():

            ce = change["CE"]
            pe = change["PE"]

            if ce["State"] == "Fresh Call Writing":
                bearish += 3
                observations.append(
                    f"Fresh Call Writing at {strike}"
                )

            elif ce["State"] == "Short Covering":
                bullish += 2

            elif ce["State"] == "Long Build-up":
                bullish += 2

            elif ce["State"] == "Long Unwinding":
                bearish += 1

            if pe["State"] == "Fresh Put Writing":
                bullish += 3
                observations.append(
                    f"Fresh Put Writing at {strike}"
                )

            elif pe["State"] == "Short Build-up":
                bearish += 2

            elif pe["State"] == "Long Build-up":
                bullish += 2

            elif pe["State"] == "Long Unwinding":
                bearish += 1

        if bullish > bearish:

            bias = "Bullish"

        elif bearish > bullish:

            bias = "Bearish"

        else:

            bias = "Neutral"

        confidence = 50

        total = bullish + bearish

        if total:

            confidence = round(
                max(bullish, bearish) / total * 100,
                1,
            )

        return {

            "Bias": bias,

            "Confidence": confidence,

            "BullishScore": bullish,

            "BearishScore": bearish,

            "Support": support,

            "Resistance": resistance,

            "Observations": observations,

        }
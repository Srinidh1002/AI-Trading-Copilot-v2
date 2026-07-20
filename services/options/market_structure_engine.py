"""
Options Market Structure Engine
"""


class MarketStructureEngine:

    @staticmethod
    def analyze(flow):

        support = flow["Support"]
        resistance = flow["Resistance"]

        pcr = flow["PCR"]

        if pcr >= 1.3:
            sentiment = "Strong Bullish"

        elif pcr >= 1.05:
            sentiment = "Bullish"

        elif pcr <= 0.70:
            sentiment = "Strong Bearish"

        elif pcr <= 0.95:
            sentiment = "Bearish"

        else:
            sentiment = "Neutral"

        width = resistance - support

        if width <= 100:
            volatility = "Low"

        elif width <= 300:
            volatility = "Medium"

        else:
            volatility = "High"

        return {

            "Sentiment": sentiment,

            "Volatility": volatility,

            "Support": support,

            "Resistance": resistance,

            "TradingRange": width,

        }
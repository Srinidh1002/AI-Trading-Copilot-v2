"""
Trading Session Engine
"""

from datetime import datetime


class TradingSessionEngine:

    @staticmethod
    def get_session():

        now = datetime.now().time()

        if now.hour < 9 or (now.hour == 9 and now.minute < 15):
            return "PRE_MARKET"

        if now.hour < 11:
            return "OPENING"

        if now.hour < 14:
            return "TREND"

        if now.hour < 15 or (now.hour == 15 and now.minute <= 15):
            return "CLOSING"

        return "MARKET_CLOSED"

    @staticmethod
    def trading_allowed():

        session = TradingSessionEngine.get_session()

        return session in [
            "OPENING",
            "TREND",
            "CLOSING",
        ]
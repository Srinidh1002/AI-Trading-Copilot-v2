"""
Market Report Engine
"""


class MarketReportEngine:

    @staticmethod
    def generate(
        decision,
        risk,
        validation,
        guard,
    ):

        report = {
            "Decision": decision["Action"],
            "Confidence": decision["Confidence"],
            "SignalStrength": decision["SignalStrength"],
            "PCR": decision["PCR"],
            "Support": decision["Support"],
            "Resistance": decision["Resistance"],
            "TradingZone": decision["TradingZone"],
            "Risk": risk,
            "TradeValidation": validation,
            "MarketGuard": guard,
            "Reasons": decision["Reasons"],
            "SmartMoney": decision["SmartMoney"],
            "MarketStructure": decision["MarketStructure"],
        }

        return report
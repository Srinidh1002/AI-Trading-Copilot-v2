"""
Live Trading AI
"""

import time

from services.ai.trading_ai import TradingAI


class LiveTradingAI:

    def __init__(
        self,
        symbol="NIFTY",
        spot=24346.7,
        levels=10,
        interval=30,
    ):

        self.symbol = symbol
        self.spot = spot
        self.levels = levels
        self.interval = interval

        self.ai = TradingAI()

    def start(self):

        print("=" * 80)
        print("Initializing AI...")
        print("=" * 80)

        self.ai.initialize(
            self.symbol,
            self.spot,
            self.levels,
        )

        try:

            while True:

                print("\n" + "=" * 80)

                report = self.ai.analyze(
                    self.symbol,
                    self.spot,
                    self.levels,
                )

                print(f"Decision     : {report['Decision']}")
                print(f"Confidence   : {report['Confidence']}%")
                print(f"PCR          : {report['PCR']}")
                print(f"Support      : {report['Support']}")
                print(f"Resistance   : {report['Resistance']}")
                print(f"Signal       : {report['SignalStrength']}")
                print(f"Trade        : {report['TradeValidation']['TradeAllowed']}")
                print(f"Guard        : {report['MarketGuard']['Level']}")

                print("\nReasons")

                for reason in report["Reasons"]:
                    print("-", reason)

                if report["TradeValidation"]["Reasons"]:

                    print("\nValidation")

                    for reason in report["TradeValidation"]["Reasons"]:
                        print("-", reason)

                time.sleep(self.interval)

        except KeyboardInterrupt:

            print("\n")
            print("=" * 80)
            print("AI stopped by user.")
            print("=" * 80)


if __name__ == "__main__":

    ai = LiveTradingAI(
        symbol="NIFTY",
        spot=24346.7,
        levels=10,
        interval=30,
    )

    ai.start()
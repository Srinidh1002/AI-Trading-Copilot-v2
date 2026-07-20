"""
Production OI Change Engine

Compares two option chain snapshots and classifies
institutional positioning.
"""


class OIChangeEngine:

    @staticmethod
    def _classify(price_change, oi_change):

        if oi_change > 0:

            if price_change > 0:
                return "Long Build-up"

            elif price_change < 0:
                return "Short Build-up"

            else:
                return "OI Build-up"

        elif oi_change < 0:

            if price_change > 0:
                return "Short Covering"

            elif price_change < 0:
                return "Long Unwinding"

            else:
                return "OI Unwinding"

        return "Neutral"

    @staticmethod
    def _strength(price_change, oi_change, volume_change):

        score = (
            abs(price_change)
            + abs(oi_change) / 100
            + abs(volume_change) / 100
        )

        return round(min(score, 100), 1)

    @staticmethod
    def analyze(previous_flow, current_flow):

        previous = previous_flow["Chain"]
        current = current_flow["Chain"]

        output = {}

        for strike in current:

            if strike not in previous:
                continue

            output[strike] = {}

            for side in ["CE", "PE"]:

                old = previous[strike].get(side)
                new = current[strike].get(side)

                if old is None or new is None:

                    output[strike][side] = {
                        "State": "Unavailable",
                        "OI Change": 0,
                        "Price Change": 0,
                        "Volume Change": 0,
                        "Strength": 0,
                    }

                    continue

                oi_change = (
                    new["opnInterest"]
                    - old["opnInterest"]
                )

                price_change = (
                    new["ltp"]
                    - old["ltp"]
                )

                volume_change = (
                    new["tradeVolume"]
                    - old["tradeVolume"]
                )

                state = OIChangeEngine._classify(
                    price_change,
                    oi_change,
                )

                strength = OIChangeEngine._strength(
                    price_change,
                    oi_change,
                    volume_change,
                )

                if side == "CE":

                    if state == "Short Build-up":
                        state = "Fresh Call Writing"

                    elif state == "Long Unwinding":
                        state = "Call Unwinding"

                else:

                    if state == "Long Build-up":
                        state = "Fresh Put Writing"

                    elif state == "Long Unwinding":
                        state = "Put Unwinding"

                output[strike][side] = {

                    "State": state,

                    "OI Change": oi_change,

                    "Price Change": round(price_change, 2),

                    "Volume Change": volume_change,

                    "Strength": strength,

                    "Current OI": new["opnInterest"],

                    "Current Price": new["ltp"],

                    "Current Volume": new["tradeVolume"],
                }

        return output
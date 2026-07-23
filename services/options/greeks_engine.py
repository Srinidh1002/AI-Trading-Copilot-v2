"""
Production Greeks Engine

Uses Angel One live Option Greeks API.
"""

from services.options.angel_option_client import (
    AngelOptionClient,
)


class GreeksEngine:

    def __init__(self):

        self.client = AngelOptionClient()

    # -----------------------------------------------------

    def analyze(
        self,
        underlying,
        expiry,
    ):

        response = self.client.get_option_greeks(
            underlying,
            expiry,
        )

        contracts = response.get(
            "data",
            [],
        )

        if not contracts:

            return {

                "Status": "Unavailable",

                "Contracts": [],

                "ATM": {},

                "Summary": {},

            }

        atm = min(

            contracts,

            key=lambda x: abs(
                float(
                    x.get(
                        "delta",
                        0,
                    )
                )
                - 0.5
            ),

        )

        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        total_iv = 0.0

        valid = 0

        normalized = []

        for contract in contracts:

            delta = float(
                contract.get(
                    "delta",
                    0,
                )
            )

            gamma = float(
                contract.get(
                    "gamma",
                    0,
                )
            )

            theta = float(
                contract.get(
                    "theta",
                    0,
                )
            )

            vega = float(
                contract.get(
                    "vega",
                    0,
                )
            )

            iv = float(
                contract.get(
                    "impliedVolatility",
                    contract.get(
                        "iv",
                        0,
                    ),
                )
            )

            rho = float(
                contract.get(
                    "rho",
                    0,
                )
            )

            total_delta += delta
            total_gamma += gamma
            total_theta += theta
            total_vega += vega
            total_iv += iv

            valid += 1

            normalized.append({

                "TradingSymbol": contract.get(
                    "tradingSymbol",
                ),

                "Strike": contract.get(
                    "strikePrice",
                ),

                "OptionType": contract.get(
                    "optionType",
                ),

                "Delta": delta,

                "Gamma": gamma,

                "Theta": theta,

                "Vega": vega,

                "IV": iv,

                "Rho": rho,

            })

        avg_delta = round(
            total_delta / valid,
            4,
        )

        avg_gamma = round(
            total_gamma / valid,
            4,
        )

        avg_theta = round(
            total_theta / valid,
            4,
        )

        avg_vega = round(
            total_vega / valid,
            4,
        )

        avg_iv = round(
            total_iv / valid,
            2,
        )

        if avg_delta > 0.20:

            bias = "Bullish"

            confidence = 80

        elif avg_delta < -0.20:

            bias = "Bearish"

            confidence = 80

        else:

            bias = "Neutral"

            confidence = 55

        return {

            "Status": "Success",

            "Contracts": normalized,

            "ATM": {

                "TradingSymbol": atm.get(
                    "tradingSymbol",
                ),

                "Strike": atm.get(
                    "strikePrice",
                ),

                "Delta": float(
                    atm.get(
                        "delta",
                        0,
                    )
                ),

                "Gamma": float(
                    atm.get(
                        "gamma",
                        0,
                    )
                ),

                "Theta": float(
                    atm.get(
                        "theta",
                        0,
                    )
                ),

                "Vega": float(
                    atm.get(
                        "vega",
                        0,
                    )
                ),

                "IV": float(
                    atm.get(
                        "impliedVolatility",
                        atm.get(
                            "iv",
                            0,
                        ),
                    )
                ),

                "Rho": float(
                    atm.get(
                        "rho",
                        0,
                    )
                ),

            },

            "Summary": {

                "AverageDelta": avg_delta,

                "AverageGamma": avg_gamma,

                "AverageTheta": avg_theta,

                "AverageVega": avg_vega,

                "AverageIV": avg_iv,

                "Bias": bias,

                "Confidence": confidence,

            },

        }
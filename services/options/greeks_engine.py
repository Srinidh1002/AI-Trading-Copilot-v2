"""
Production Greeks Engine.

Uses Angel One live Option Greeks API where the
provider capability is available.

Read-only.
No broker order submission.
"""

from services.options.angel_option_client import (
    AngelOptionClient,
)
from services.options.angel_option_provider_capabilities import (
    angel_option_provider_capabilities,
)


def _unavailable_result(
    *,
    reason,
    capability_state,
):
    return {
        "Status": "Unavailable",
        "CapabilityState": capability_state,
        "Reason": reason,
        "Contracts": [],
        "ATM": {},
        "Summary": {
            "AverageDelta": 0,
            "AverageGamma": 0,
            "AverageTheta": 0,
            "AverageVega": 0,
            "AverageIV": 0,
            "Bias": "Neutral",
            "Confidence": 0,
        },
    }


class GreeksEngine:

    def __init__(
        self,
        client=None,
    ):
        self.client = (
            client
            if client is not None
            else AngelOptionClient()
        )

    def analyze(
        self,
        underlying,
        expiry,
        option_exchange=None,
    ):
        capabilities = (
            angel_option_provider_capabilities(
                underlying,
                option_exchange,
            )
        )

        if not capabilities.option_greeks_supported:
            return _unavailable_result(
                reason=(
                    "OPTION_GREEKS_PROVIDER_CAPABILITY_UNAVAILABLE"
                ),
                capability_state="UNSUPPORTED_BY_PROVIDER",
            )

        try:
            response = self.client.get_option_greeks(
                capabilities.underlying_symbol,
                expiry,
            )
        except Exception as exc:
            return _unavailable_result(
                reason=(
                    "OPTION_GREEKS_PROVIDER_FAILURE:"
                    f"{type(exc).__name__}"
                ),
                capability_state="PROVIDER_FAILURE",
            )

        contracts = response.get(
            "data",
            [],
        )

        if not contracts:
            return _unavailable_result(
                reason="OPTION_GREEKS_DATA_UNAVAILABLE",
                capability_state="SUPPORTED",
            )

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

            normalized.append(
                {
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
                }
            )

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
            "CapabilityState": "SUPPORTED",
            "Reason": None,
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


__all__ = [
    "GreeksEngine",
]

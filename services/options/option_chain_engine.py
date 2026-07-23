"""
Production Option Chain Engine

Institutional Option Intelligence
"""

from services.options.angel_option_client import AngelOptionClient
from services.options.oi_engine import OIEngine
from services.options.oi_change_engine import OIChangeEngine
from services.options.option_flow_engine import OptionFlowEngine
from services.options.pcr_engine import PCREngine
from services.options.max_pain_engine import MaxPainEngine
from services.options.greeks_engine import GreeksEngine


class OptionChainEngine:

    _previous_snapshot = None

    def __init__(self):

        self.client = AngelOptionClient()

        self.greeks = GreeksEngine()

    # -----------------------------------------------------

    def analyze(
        self,
        underlying,
        expiry,
        spot,
    ):

        chain = self.client.get_option_chain(
            underlying,
            expiry,
            spot,
        )

        if not chain:

            return {

                "Status": "Unavailable",

                "Chain": [],

                "PCR": {},

                "OI": {},

                "OIChange": {},

                "Flow": {},

                "MaxPain": {},

                "Greeks": {},

            }

        option_data = {

            "data": {

                "fetched": chain,

            }

        }

        token_map = {}

        for option in chain:

            token = option.get(
                "symbolToken"
            )

            strike = option.get(
                "strikePrice"
            )

            if token is not None:

                token_map[token] = strike

        flow_input = {

            "quotes": {

                "data": {

                    "fetched": chain,

                }

            },

            "token_to_strike": token_map,

        }

        pcr = PCREngine.analyze(
            option_data
        )

        oi = OIEngine.analyze(
            option_data
        )

        flow = OptionFlowEngine.analyze(
            flow_input
        )

        max_pain = MaxPainEngine.analyze(
            flow_input
        )

        greeks = self.greeks.analyze(
            underlying,
            expiry,
        )

        current_snapshot = {

            "Chain": flow["Chain"]

        }

        if OptionChainEngine._previous_snapshot is None:

            oi_change = {}

        else:

            oi_change = OIChangeEngine.analyze(

                OptionChainEngine._previous_snapshot,

                current_snapshot,

            )

        OptionChainEngine._previous_snapshot = current_snapshot

        return {

            "Status": "Success",

            "Chain": chain,

            "PCR": pcr,

            "OI": oi,

            "OIChange": oi_change,

            "Flow": flow,

            "Greeks": greeks,

            "MaxPain": max_pain,

            "Support": flow["Support"],

            "Resistance": flow["Resistance"],

            "MaxPainStrike": flow["MaxPain"],

            "Bias": flow["Bias"],

            "Confidence": max(
                flow.get("Confidence", 0),
                greeks.get("Summary", {}).get(
                    "Confidence",
                    0,
                ),
            ),

        }
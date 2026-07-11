"""
Safety-gated live option decision pipeline.

Flow:
1. Analyse the underlying market.
2. Stop immediately if decision is NO_TRADE.
3. If TRADE, build the live option chain.
4. Select the best CE or PE contract.

Read-only. No orders are placed.
"""

from services.live_analysis_pipeline import (
    LiveAnalysisPipeline,
)

from services.live_option_chain_builder import (
    LiveOptionChainBuilder,
)

from services.option_contract_selector import (
    select_option_contract,
)


class LiveOptionDecisionPipeline:
    """Combine market analysis and option contract selection."""

    def __init__(
        self,
        analysis_pipeline=None,
        option_chain_builder=None,
    ):
        self.analysis_pipeline = (
            analysis_pipeline
            if analysis_pipeline is not None
            else LiveAnalysisPipeline()
        )

        self.option_chain_builder = (
            option_chain_builder
            if option_chain_builder is not None
            else LiveOptionChainBuilder()
        )

    def analyse(
        self,
        exchange,
        symboltoken,
        underlying,
        spot_price,
        strikes_each_side=5,
        end_time=None,
    ):
        """
        Run the complete safety-gated option decision pipeline.
        """

        if spot_price <= 0:
            raise ValueError(
                "Spot price must be greater than zero."
            )

        # ---------------------------------
        # MARKET ANALYSIS
        # ---------------------------------

        market_result = (
            self.analysis_pipeline.analyse(
                exchange=exchange,
                symboltoken=symboltoken,
                end_time=end_time,
            )
        )

        strategy = market_result.get(
            "strategy",
            {},
        )

        market_decision = str(
            strategy.get(
                "decision",
                "NO_TRADE",
            )
        ).upper()

        direction = str(
            strategy.get(
                "direction",
                "NEUTRAL",
            )
        ).upper()

        # ---------------------------------
        # SAFETY GATE
        # ---------------------------------

        if market_decision != "TRADE":
            return {
                "decision": "NO_TRADE",
                "market_decision": market_decision,
                "direction": direction,
                "market_analysis": market_result,
                "option_chain": None,
                "contract": {
                    "selected": False,
                    "decision": "NO_CONTRACT",
                    "symbol": None,
                    "strike": None,
                    "option_type": None,
                    "expiry": None,
                    "premium": None,
                    "score": 0,
                    "reasons": [
                        "Market analysis did not authorize a trade."
                    ],
                },
            }

        if direction not in {
            "BULLISH",
            "BEARISH",
        }:
            return {
                "decision": "NO_TRADE",
                "market_decision": market_decision,
                "direction": direction,
                "market_analysis": market_result,
                "option_chain": None,
                "contract": {
                    "selected": False,
                    "decision": "NO_CONTRACT",
                    "symbol": None,
                    "strike": None,
                    "option_type": None,
                    "expiry": None,
                    "premium": None,
                    "score": 0,
                    "reasons": [
                        "Trade was authorized without a valid direction."
                    ],
                },
            }

        # ---------------------------------
        # BUILD LIVE OPTION CHAIN
        # ---------------------------------

        option_chain = (
            self.option_chain_builder.build_chain(
                underlying=underlying,
                spot_price=spot_price,
                strikes_each_side=strikes_each_side,
            )
        )

        contracts = option_chain.get(
            "contracts",
            [],
        )

        # ---------------------------------
        # SELECT BEST CONTRACT
        # ---------------------------------

        contract = select_option_contract(
            contracts=contracts,
            direction=direction,
            spot_price=spot_price,
            require_delta=False,
        )

        # ---------------------------------
        # FINAL DECISION
        # ---------------------------------

        if not contract.get(
            "selected",
            False,
        ):
            final_decision = "NO_TRADE"

        else:
            final_decision = "TRADE_READY"

        return {
            "decision": final_decision,
            "market_decision": market_decision,
            "direction": direction,
            "market_analysis": market_result,
            "option_chain": option_chain,
            "contract": contract,
        }
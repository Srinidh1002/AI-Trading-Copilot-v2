"""
Trading Orchestrator

Coordinates the complete AI trading pipeline.
"""

from typing import Dict

from services.market_ranking_engine import (
    rank_markets,
    best_market,
)

from services.learning_engine import learning_engine
from services.performance_engine import performance_engine


class TradingOrchestrator:

    def __init__(self):
        pass

    def run(
        self,
        market_results: Dict[str, Dict],
    ) -> Dict:

        rankings = rank_markets(
            market_results
        )

        best_trade = best_market(
            market_results
        )

        performance = performance_engine.report()

        market_count = len(rankings)

        buy_count = sum(
            1
            for x in rankings
            if x["signal"] == "BUY"
        )

        sell_count = sum(
            1
            for x in rankings
            if x["signal"] == "SELL"
        )

        hold_count = sum(
            1
            for x in rankings
            if x["signal"] == "HOLD"
        )

        market_bias = "NEUTRAL"

        if buy_count > sell_count:
            market_bias = "BULLISH"

        elif sell_count > buy_count:
            market_bias = "BEARISH"

        learning_engine.record_trade({

            "market": best_trade.get("market"),

            "signal": best_trade.get("signal"),

            "confidence": best_trade.get("confidence"),

            "result": "PENDING",

        })

        return {

            "market_bias": market_bias,

            "performance": performance,

            "best_trade": best_trade,

            "rankings": rankings,

            "markets_analyzed": market_count,

            "buy_markets": buy_count,

            "sell_markets": sell_count,

            "hold_markets": hold_count,

        }


def run_trading_pipeline(
    market_results: Dict[str, Dict],
) -> Dict:

    return TradingOrchestrator().run(
        market_results
    )
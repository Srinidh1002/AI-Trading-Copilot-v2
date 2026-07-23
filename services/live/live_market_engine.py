"""
Live Market Engine

Central orchestration engine for real-time market
analysis and trading.

Responsibilities
----------------
✓ Live Market Data
✓ Technical Analysis
✓ Sentiment Analysis
✓ Option Chain Analysis
✓ AI Decision Engine
✓ Risk Validation
✓ Trade Execution
✓ Portfolio Updates
✓ Notifications
✓ Continuous Live Loop
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from services.ai.ai_engine import AIEngine
from services.analysis.market_engine import MarketEngine
from services.analysis.option_ai import OptionAI
from services.analysis.sentiment import SentimentAnalyzer
from services.analysis.technical import TechnicalAnalyzer
from services.core.final_decision_pipeline import FinalDecisionPipeline
from services.execution.order_executor import OrderExecutor
from services.execution.order_manager import OrderManager
from services.notifications.notification_manager import NotificationManager
from services.portfolio.portfolio_manager import PortfolioManager
from services.risk.risk_manager import RiskManager
from services.market.market_data import MarketDataService


class LiveMarketEngine:

    def __init__(self):

        self.market = MarketDataService()

        self.technical = TechnicalAnalyzer()

        self.sentiment = SentimentAnalyzer()

        self.option_ai = OptionAI()

        self.market_engine = MarketEngine()

        self.ai = AIEngine()

        self.pipeline = FinalDecisionPipeline()

        self.risk = RiskManager()

        self.executor = OrderExecutor()

        self.order_manager = OrderManager()

        self.portfolio = PortfolioManager()

        self.notification = NotificationManager()

        self.running = False

        self.last_snapshot: dict[str, Any] = {}

    # --------------------------------------------------

    def build_snapshot(

        self,

        symbol: str,

    ) -> dict[str, Any]:

        market = self.market.get_market_data(symbol)

        technical = self.technical.calculate_indicators(symbol)

        sentiment = self.sentiment.sentiment_score(symbol)

        option_chain = self.option_ai.option_score(symbol)

        market_score = self.market_engine.market_score(symbol)

        snapshot = {

            "symbol": symbol,

            "timestamp": datetime.now().isoformat(),

            "market": market,

            "technical": technical,

            "sentiment": sentiment,

            "option_chain": option_chain,

            "market_score": market_score,

        }

        self.last_snapshot = snapshot

        return snapshot

    # --------------------------------------------------

    def ai_decision(

        self,

        snapshot: dict[str, Any],

    ):

        return self.ai.analyze(snapshot)

    # --------------------------------------------------

    def final_decision(

        self,

        snapshot: dict[str, Any],

        ai_result: dict[str, Any],

    ):

        return self.pipeline.process(

            snapshot,

            ai_result,

        )

    # --------------------------------------------------

    def execute(

        self,

        decision: dict[str, Any],

    ):

        if not decision.get(

            "execute",

            False,

        ):

            return {

                "status": "SKIPPED",

            }

        if not self.risk.validate_trade(

            decision,

        ):

            return {

                "status": "BLOCKED",

            }

        order = self.executor.execute(

            decision,

        )

        self.order_manager.record(order)

        self.portfolio.update(order)

        self.notification.trade_notification(

            order,

        )

        return order

    # --------------------------------------------------

    def process_symbol(

        self,

        symbol: str,

    ):

        snapshot = self.build_snapshot(symbol)

        ai_result = self.ai_decision(snapshot)

        decision = self.final_decision(

            snapshot,

            ai_result,

        )

        execution = self.execute(decision)

        return {

            "snapshot": snapshot,

            "ai": ai_result,

            "decision": decision,

            "execution": execution,

        }

    # --------------------------------------------------

    def start(

        self,

        symbols: list[str],

        interval_seconds: int = 5,

    ):

        self.running = True

        while self.running:

            for symbol in symbols:

                try:

                    self.process_symbol(symbol)

                except Exception as exc:

                    self.notification.error(

                        str(exc),

                    )

            time.sleep(interval_seconds)

    # --------------------------------------------------

    def stop(self):

        self.running = False

    # --------------------------------------------------

    def status(self):

        return {

            "running": self.running,

            "last_snapshot_time": self.last_snapshot.get(

                "timestamp",

            ),

            "last_symbol": self.last_snapshot.get(

                "symbol",

            ),

        }

    # --------------------------------------------------

    def summary(self):

        return {

            "running": self.running,

            "last_snapshot": self.last_snapshot,

        }


# ------------------------------------------------------
# Standalone Execution
# ------------------------------------------------------

if __name__ == "__main__":

    engine = LiveMarketEngine()

    print("Live Market Engine Ready")
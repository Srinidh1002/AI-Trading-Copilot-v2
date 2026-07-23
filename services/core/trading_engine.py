"""
Trading Engine

Central orchestration engine for the complete
AI Trading Copilot pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

from services.core.market_snapshot import get_market_snapshot
from services.core.final_decision_pipeline import FinalDecisionPipeline

from services.risk.risk_engine import calculate_risk
from services.risk.position_sizing_engine import PositionSizingEngine

from services.execution.trade_validator import TradeValidator
from services.execution.market_guard import MarketGuard
from services.execution.trading_session_engine import TradingSessionEngine
from services.execution.order_manager import OrderManager
from services.execution.order_tracker import OrderTracker

LOGGER = logging.getLogger(__name__)


class TradingEngine:

    def __init__(self):

        self.order_manager = OrderManager()

        self.order_tracker = OrderTracker()

    # ---------------------------------------------------------

def run(
    self,
    capital: float,
) -> dict:

    # ----------------------------------
    # Build Institutional Snapshot
    # ----------------------------------

    snapshot = get_market_snapshot()

    snapshot = FinalDecisionPipeline.run(
        snapshot
    )

    decision = snapshot["final_decision"]

    # ----------------------------------
    # Risk
    # ----------------------------------

    risk = calculate_risk(
        snapshot,
        decision,
    )

    snapshot["risk"] = risk

    # ----------------------------------
    # Position Size
    # ----------------------------------

    sizing = PositionSizingEngine.calculate(

        capital=capital,

        confidence=decision.get(
            "confidence",
            50,
        ),

        atr=snapshot["indicators"]["ATR"],

        entry=risk["entry"],

        stoploss=risk["stop_loss"],

    )

    # ----------------------------------
    # Order
    # ----------------------------------

    order = {

        "symbol": "NIFTY",

        "signal": decision["signal"],

        "quantity": sizing["quantity"],

        "order_type": "MARKET",

        "product": "INTRADAY",

        "price": None,

        "stop_loss": risk["stop_loss"],

        "target": risk["target"],

    }

    # ----------------------------------
    # Execution Pipeline
    # ----------------------------------

    TradeValidator.validate(order)

    MarketGuard.validate()

    TradingSessionEngine.validate()

    result = self.order_manager.submit_order(
        order
    )

    if result.get("success"):

        self.order_tracker.register(

            result["order_id"],

            order,

        )

        self.order_tracker.update_status(

            result["order_id"],

            result["status"],

        )

    # ----------------------------------
    # Return
    # ----------------------------------

    return {

        "snapshot": snapshot,

        "decision": decision,

        "risk": risk,

        "position": sizing,

        "execution": result,

        "orders": self.order_tracker.summary(),

    }
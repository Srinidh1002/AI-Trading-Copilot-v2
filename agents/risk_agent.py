"""
Risk-management agent.

Wraps the lot-based risk engine and returns
a structured RiskState.

No orders are placed.
"""

from models.risk_state import (
    RiskState,
)

from services.risk_engine import (
    calculate_trade_risk,
)


class RiskAgent:

    def analyse(
        self,
        capital,
        entry_price,
        stop_loss_price,
        target_price,
        lot_size,
        **kwargs,
    ):
        result = calculate_trade_risk(
            capital=capital,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            target_price=target_price,
            lot_size=lot_size,
            **kwargs,
        )

        return RiskState(
            **result
        )
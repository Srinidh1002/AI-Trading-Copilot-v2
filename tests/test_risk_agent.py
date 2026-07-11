"""
Risk-management agent.

Supports:
1. Existing strategy and account-level risk evaluation.
2. Lot-based option position sizing.

No orders are placed.
"""

from models.risk_state import (
    RiskState,
)

from services.risk_engine import (
    evaluate_trade_risk,
    calculate_trade_risk,
)


class RiskAgent:

    def analyse(
        self,
        strategy,
        capital,
        entry_price,
        stop_loss,
        target_price,
        **kwargs,
    ):
        """
        Existing strategy-level risk evaluation.
        """

        result = evaluate_trade_risk(
            strategy=strategy,
            capital=capital,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
            **kwargs,
        )

        return RiskState(
            approved=result["approved"],
            decision=result["decision"],
            position_size=result[
                "position_size"
            ],
            risk_amount=result[
                "risk_amount"
            ],
            risk_reward_ratio=result[
                "risk_reward_ratio"
            ],
            reasons=result["reasons"],
            warnings=result["warnings"],
        )

    def analyse_position_size(
        self,
        capital,
        entry_price,
        stop_loss_price,
        target_price,
        lot_size,
        **kwargs,
    ):
        """
        Lot-based option position sizing.
        """

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
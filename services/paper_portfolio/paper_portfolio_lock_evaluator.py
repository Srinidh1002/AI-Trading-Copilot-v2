"""Pure deterministic P8 portfolio lock evaluation."""
from __future__ import annotations

from datetime import datetime

from services.contracts.paper_portfolio_lock_state_v1 import (
    PaperPortfolioLockStateV1,
)
from services.contracts.paper_portfolio_policy_v1 import PaperPortfolioPolicyV1


def evaluate_paper_portfolio_locks(
    *,
    policy: PaperPortfolioPolicyV1,
    trading_day_id: str,
    daily_realized_net_pnl: float,
    current_unrealized_pnl: float,
    total_equity: float,
    previous_lock_state: PaperPortfolioLockStateV1 | None,
    evaluated_at: datetime,
) -> PaperPortfolioLockStateV1:
    """Return a latched PAPER-only lock state without mutating inputs."""
    if type(policy) is not PaperPortfolioPolicyV1:
        raise TypeError("policy must be exact PaperPortfolioPolicyV1")
    if previous_lock_state is not None and type(previous_lock_state) is not PaperPortfolioLockStateV1:
        raise TypeError("previous_lock_state must be exact PaperPortfolioLockStateV1 or None")
    if type(trading_day_id) is not str or not trading_day_id.strip():
        raise ValueError("trading_day_id must be nonblank")
    if previous_lock_state is not None and previous_lock_state.trading_day_id != trading_day_id:
        previous_lock_state = None

    daily_total_pnl = float(daily_realized_net_pnl) + float(current_unrealized_pnl)
    daily_loss_amount = max(0.0, -daily_total_pnl)
    previous_peak = (
        float(total_equity)
        if previous_lock_state is None
        else previous_lock_state.intraday_peak_equity
    )
    intraday_peak_equity = max(previous_peak, float(total_equity))
    daily_drawdown_amount = max(0.0, intraday_peak_equity - float(total_equity))

    prior_loss_locked = False if previous_lock_state is None else previous_lock_state.loss_locked
    prior_profit_locked = False if previous_lock_state is None else previous_lock_state.profit_locked

    loss_locked = prior_loss_locked or (
        policy.loss_lock_enabled
        and (
            daily_loss_amount >= policy.maximum_daily_loss_amount
            or daily_drawdown_amount >= policy.maximum_daily_drawdown_amount
        )
    )
    profit_locked = prior_profit_locked or (
        policy.profit_lock_enabled
        and policy.minimum_daily_realized_profit_to_lock is not None
        and float(daily_realized_net_pnl)
        >= policy.minimum_daily_realized_profit_to_lock
    )

    reasons: list[str] = []
    if loss_locked:
        if daily_loss_amount >= policy.maximum_daily_loss_amount:
            reasons.append("DAILY_LOSS_LIMIT")
        if daily_drawdown_amount >= policy.maximum_daily_drawdown_amount:
            reasons.append("DAILY_DRAWDOWN_LIMIT")
        if prior_loss_locked and not reasons:
            reasons.append("DAILY_LOSS_LOCK_LATCHED")
    if profit_locked:
        reasons.append("PROFIT_LOCK")

    return PaperPortfolioLockStateV1(
        trading_day_id=trading_day_id.strip(),
        loss_locked=loss_locked,
        profit_locked=profit_locked,
        lock_reason_codes=tuple(reasons),
        daily_total_pnl=daily_total_pnl,
        daily_realized_net_pnl=float(daily_realized_net_pnl),
        daily_loss_amount=daily_loss_amount,
        intraday_peak_equity=intraday_peak_equity,
        daily_drawdown_amount=daily_drawdown_amount,
        evaluated_at=evaluated_at,
        loss_locked_at=(
            previous_lock_state.loss_locked_at
            if prior_loss_locked
            else evaluated_at if loss_locked else None
        ),
        profit_locked_at=(
            previous_lock_state.profit_locked_at
            if prior_profit_locked
            else evaluated_at if profit_locked else None
        ),
    )

"""Read-only Trades and P&L center over published PAPER read models."""
from __future__ import annotations

from typing import Any

from services.dashboard_read_models import (
    DashboardApplicationViewV1,
    DashboardPaperPositionDetailViewV1,
)


def filter_paper_trades(
    trades: tuple[DashboardPaperPositionDetailViewV1, ...], *,
    market: str = "ALL", status: str = "ALL",
) -> tuple[DashboardPaperPositionDetailViewV1, ...]:
    """Pure display filter; it never changes published trade state."""
    if type(trades) is not tuple:
        raise TypeError("trades")
    if any(type(item) is not DashboardPaperPositionDetailViewV1 for item in trades):
        raise TypeError("trades")
    market, status = market.upper(), status.upper()
    if market not in {"ALL", "NIFTY", "SENSEX"} or status not in {"ALL", "OPEN", "CLOSED"}:
        raise ValueError("filter")
    return tuple(
        item for item in trades
        if (market == "ALL" or item.market == market)
        and (status == "ALL" or (status == "CLOSED") == item.is_terminal)
    )


def render_trades_pnl_center(*, st: Any, view: DashboardApplicationViewV1) -> None:
    if type(view) is not DashboardApplicationViewV1:
        raise TypeError("view")
    st.subheader("TRADES & P&L CENTER")
    st.caption("Read-only persisted PAPER trades, fills, and portfolio state.")
    _render_portfolio(st, view)
    trades = _all_trades(view)
    open_trades = filter_paper_trades(trades, status="OPEN")
    closed_trades = filter_paper_trades(trades, status="CLOSED")
    _render_section(st, "OPEN PAPER POSITIONS", open_trades)
    _render_section(st, "CLOSED PAPER TRADES", closed_trades)
    _render_section(st, "ALL PUBLISHED PAPER HISTORY", trades)


def _all_trades(view: DashboardApplicationViewV1) -> tuple[DashboardPaperPositionDetailViewV1, ...]:
    active = view.active_paper_position
    if active is None or any(item.paper_trade_id == active.paper_trade_id for item in view.paper_trade_history):
        return view.paper_trade_history
    return (active,) + view.paper_trade_history


def _render_portfolio(st: Any, view: DashboardApplicationViewV1) -> None:
    portfolio = view.portfolio
    if portfolio is None:
        st.info("No published PAPER portfolio summary is available.")
        return
    st.write(
        f"Starting capital: {portfolio.starting_capital} | Available cash: {portfolio.available_cash} | "
        f"Reserved: {portfolio.reserved_capital} | Deployed: {portfolio.deployed_capital} | Committed: {portfolio.committed_capital}"
    )
    st.write(
        f"Realized net P&L: {portfolio.realized_net_pnl} | Unrealized P&L: {portfolio.unrealized_pnl} | "
        f"Total P&L: {portfolio.total_pnl} | Total equity: {portfolio.total_equity}"
    )
    st.write(
        f"Open positions: {portfolio.open_position_count} | Pending plans: {portfolio.pending_plan_count} | "
        f"Concurrent trades: {portfolio.concurrent_trade_count} | Aggregate committed risk: {portfolio.aggregate_committed_risk}"
    )


def _render_section(st: Any, title: str, trades: tuple[DashboardPaperPositionDetailViewV1, ...]) -> None:
    st.subheader(title)
    if not trades:
        st.info("No published PAPER trades are available.")
        return
    for trade in trades:
        st.write(
            f"{trade.paper_trade_id} | {trade.market or 'Unavailable'} | {trade.option_symbol or 'Unavailable'} | "
            f"{trade.lifecycle_state} | entry {trade.entry_price} | current/exit {trade.current_option_price} | "
            f"quantity {trade.remaining_quantity} | realized {trade.realized_net_pnl} | unrealized {trade.unrealized_pnl} | total {trade.total_pnl}"
        )
        st.write(f"Stop: {trade.stop_loss} | T1: {trade.target_1} | T2: {trade.target_2} | T3: {trade.target_3} | Terminal: {trade.terminal_reason or '—'}")
        for fill in trade.fills:
            st.write(
                f"Fill {fill.filled_at.isoformat()} | {fill.fill_type} | {fill.fill_reason} | {fill.target_name or '—'} | "
                f"{fill.side} | lots {fill.filled_lot_count} | quantity {fill.filled_quantity} | price {fill.fill_price} | "
                f"cost {fill.estimated_trading_cost} | cash {fill.net_cash_effect}"
            )

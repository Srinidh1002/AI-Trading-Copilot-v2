"""Read-only Streamlit rendering for the five-market PAPER campaign."""
from __future__ import annotations

from dashboard.five_market_campaign_sync_v2 import get_five_market_campaign_view


def render_five_market_certification_center(*, st, state) -> None:
    view = get_five_market_campaign_view(state)

    st.subheader("FIVE-MARKET PAPER CAMPAIGN")

    if view is None:
        st.info("Five-market campaign projection is unavailable.")
        return

    st.caption(
        "PAPER ONLY · operational P&L and certification /100 are separate authorities · "
        "dashboard refresh has no trading authority"
    )

    st.write(
        f"Execution mode: {view.execution_mode} | "
        f"Broker submission: {view.broker_submission} | "
        f"Live execution: {view.live_execution}"
    )

    rows = []
    for market in view.markets:
        rows.append(
            {
                "Market": market.market,
                "Authority": market.authority_status,
                "Certification": (
                    f"{market.certification_count}/100"
                    if market.certification_count is not None
                    else "HOLD"
                ),
                "T1_FIRST wins": market.certification_wins,
                "SL_FIRST losses": market.certification_losses,
                "Counted IDs": market.counted_id_count,
                "Operational trades": market.operational_total_trades,
                "Operational P&L": market.operational_total_pnl,
                "Active": market.active_position_count,
                "Noncountable": market.noncountable_completed_count,
                "Ambiguous": market.ambiguous_completed_count,
                "Epoch": market.certification_epoch,
                "Strategy": market.strategy_version,
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    for market in view.markets:
        if market.authority_status != "PASS":
            st.warning(f"{market.market}: {market.authority_reason}")
            continue
        if market.latest_completed_trade_id:
            st.caption(
                f"{market.market} latest completed: "
                f"{market.latest_completed_trade_id} · "
                f"first-touch={market.latest_completed_first_touch} · "
                f"net P&L={market.latest_completed_net_pnl}"
            )

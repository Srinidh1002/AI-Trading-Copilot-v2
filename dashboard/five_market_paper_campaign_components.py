"""Read-only rendering of current five-market PAPER campaign authority."""
from __future__ import annotations

from services.dashboard_read_models.five_market_paper_campaign_view_v1 import (
    FiveMarketPaperCampaignViewV1,
)


def render_five_market_paper_campaign(*, st, view) -> None:
    st.subheader("Five-Market PAPER Campaign")

    if view is None:
        st.info("Current five-market campaign authority is unavailable.")
        return
    if type(view) is not FiveMarketPaperCampaignViewV1:
        raise TypeError("view")

    st.caption(
        "READ ONLY · PAPER ONLY · accepted certification trades are separate "
        "from operational trades/P&L"
    )

    for market in view.markets:
        with st.expander(
            f"{market.market} — {market.certification_counter}/"
            f"{market.target_trade_count}",
            expanded=(market.active_position_count > 0),
        ):
            a, b, c, d = st.columns(4)
            a.metric(
                "Accepted / 100",
                f"{market.certification_counter}/"
                f"{market.target_trade_count}",
            )
            b.metric("T1_FIRST wins", str(market.certification_wins))
            c.metric("SL_FIRST losses", str(market.certification_losses))
            d.metric(
                "Operational P&L",
                f"₹{market.operational_net_pnl:,.2f}",
            )

            st.write(
                f"Strategy: {market.strategy_version} | "
                f"Epoch: {market.certification_epoch}"
            )
            st.write(
                "Operational completed: "
                f"{market.operational_completed_trades} | "
                "Noncountable completed: "
                f"{market.noncountable_completed_trades} | "
                "Active positions: "
                f"{market.active_position_count}"
            )

            if market.active_position_count:
                st.write(
                    f"Active trade: {market.active_trade_id or 'Unavailable'} | "
                    f"First touch: {market.active_first_touch or 'NONE'}"
                )

            if market.warnings:
                for warning in market.warnings:
                    st.warning(warning)

    st.write(
        "Accepted certification trades across five markets: "
        f"{view.total_accepted_certification_trades}"
    )
    st.write(
        f"Operational P&L across five markets: "
        f"₹{view.total_operational_pnl:,.2f}"
    )
    st.caption(
        f"Release: {view.release_commit} | "
        f"Generated: {view.generated_at.isoformat()}"
    )

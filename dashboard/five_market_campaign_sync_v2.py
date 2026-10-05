"""Session-state synchronization for the read-only five-market campaign view."""
from __future__ import annotations

from pathlib import Path

from services.paper_orchestration.five_market_campaign_read_model_v2 import (
    FiveMarketCampaignViewV2,
    build_five_market_campaign_view_v2,
)

FIVE_MARKET_CAMPAIGN_VIEW_STATE_KEY = "five_market_campaign_view_v2"


def synchronize_five_market_campaign_projection(
    state,
    *,
    repo_root: str | Path,
) -> FiveMarketCampaignViewV2:
    view = build_five_market_campaign_view_v2(repo_root)
    state[FIVE_MARKET_CAMPAIGN_VIEW_STATE_KEY] = view
    return view


def get_five_market_campaign_view(state) -> FiveMarketCampaignViewV2 | None:
    value = state.get(FIVE_MARKET_CAMPAIGN_VIEW_STATE_KEY)
    if value is None:
        return None
    if type(value) is not FiveMarketCampaignViewV2:
        raise TypeError(FIVE_MARKET_CAMPAIGN_VIEW_STATE_KEY)
    return value

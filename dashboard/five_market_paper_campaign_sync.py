"""Read-only Streamlit projection sync for the five-market PAPER campaign."""
from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path

from services.reporting.five_market_paper_campaign_reader_v1 import (
    FiveMarketPaperCampaignReadError,
    build_five_market_paper_campaign_view_v1,
)


FIVE_MARKET_CAMPAIGN_STATE_KEY = "five_market_paper_campaign_view_v1"
FIVE_MARKET_CAMPAIGN_ERROR_KEY = "five_market_paper_campaign_view_error_v1"


def synchronize_five_market_paper_campaign_projection(
    state: MutableMapping[str, object],
    *,
    repo_root: str | Path = ".",
):
    """Refresh only the immutable dashboard projection; never mutate trading state."""
    if not isinstance(state, MutableMapping):
        raise TypeError("state")

    try:
        view = build_five_market_paper_campaign_view_v1(repo_root)
    except (FiveMarketPaperCampaignReadError, OSError, ValueError) as exc:
        state.pop(FIVE_MARKET_CAMPAIGN_STATE_KEY, None)
        state[FIVE_MARKET_CAMPAIGN_ERROR_KEY] = (
            f"{type(exc).__name__}:{str(exc)}"
        )
        return None

    state[FIVE_MARKET_CAMPAIGN_STATE_KEY] = view
    state.pop(FIVE_MARKET_CAMPAIGN_ERROR_KEY, None)
    return view


def get_five_market_paper_campaign_projection(state):
    return state.get(FIVE_MARKET_CAMPAIGN_STATE_KEY)

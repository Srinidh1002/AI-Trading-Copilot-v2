"""Thin isolated facade for four-market opportunity ranking."""
from __future__ import annotations

from services.contracts.four_market_opportunity_ranking_result_v1 import FourMarketOpportunityRankingResultV1
from services.contracts.four_market_ranking_policy_v1 import (
    DEFAULT_FOUR_MARKET_RANKING_POLICY,
    FourMarketRankingPolicyV1,
)
from services.contracts.market_opportunity_candidate_v1 import MarketOpportunityCandidateV1

from .aggregate import rank_four_market_opportunities


def evaluate_four_market_opportunity_ranking(
    candidates: tuple[MarketOpportunityCandidateV1, ...],
    policy: FourMarketRankingPolicyV1 = DEFAULT_FOUR_MARKET_RANKING_POLICY,
) -> FourMarketOpportunityRankingResultV1:
    """Delegate unchanged to the isolated aggregate exactly once."""
    if type(candidates) is not tuple:
        raise TypeError("candidates")
    if type(policy) is not FourMarketRankingPolicyV1:
        raise TypeError("policy")
    return rank_four_market_opportunities(candidates, policy)

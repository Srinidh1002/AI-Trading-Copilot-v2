from dataclasses import replace

import pytest

from services.contracts.four_market_opportunity_ranking_result_v1 import FourMarketOpportunityRankingResultV1
from services.opportunity_ranking import (
    evaluate_four_market_opportunity_ranking,
    rank_four_market_opportunities,
)
from tests.fixtures.p5_10j_market_regime_replay import IDENTITIES
from tests.test_market_opportunity_candidate_v1 import make_candidate


def candidates():
    return tuple(make_candidate(identity) for identity in IDENTITIES)


def test_public_api_constructs_exact_result_with_all_ineligible_candidates():
    result = rank_four_market_opportunities(candidates()[::-1])
    assert type(result) is FourMarketOpportunityRankingResultV1
    assert result.candidates and tuple((candidate.underlying_symbol, candidate.exchange) for candidate in result.candidates) == IDENTITIES
    assert result.tie_state == "ALL_INELIGIBLE"
    assert result.selected_market is None and result.selected_candidate is None
    assert result.selection_confidence == 0.0
    assert all(rank is None for rank in result.rank_by_market.values())
    assert result.to_dict() == result.to_dict()
    assert result.to_json() == result.to_json()
    assert result.semantic_dict() == result.semantic_dict()


def test_input_validation_timestamp_provenance_and_service_delegation():
    values = candidates()
    with pytest.raises(TypeError):
        rank_four_market_opportunities(list(values))
    with pytest.raises(ValueError):
        rank_four_market_opportunities(values[:3])
    with pytest.raises(ValueError):
        rank_four_market_opportunities((values[0], values[0], values[2], values[3]))
    with pytest.raises(ValueError):
        rank_four_market_opportunities((replace(values[0], evaluated_at=values[0].evaluated_at.replace(year=2027)),) + values[1:])
    assert evaluate_four_market_opportunity_ranking(values).semantic_dict() == rank_four_market_opportunities(values).semantic_dict()

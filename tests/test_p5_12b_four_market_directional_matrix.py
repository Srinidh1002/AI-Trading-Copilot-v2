import pytest

from tests.fixtures.p5_12 import *


@pytest.mark.parametrize('scenario', (STRONG_BULLISH,STRONG_BEARISH,WEAK_BULLISH,WEAK_BEARISH,RANGE_BOUND,HIGH_VOLATILITY,CONFLICTING,BLOCKED,UNAVAILABLE),ids=lambda scenario:scenario.scenario_name)
def test_homogeneous_four_market_replay_preserves_every_market_slot(scenario):
 scenarios={identity:scenario for identity in CANONICAL_MARKET_IDENTITIES}
 result=build_ranked_four_market_result(scenarios)
 assert tuple((candidate.underlying_symbol,candidate.exchange) for candidate in result.candidates)==CANONICAL_MARKET_IDENTITIES
 assert result.execution_mode=='PAPER' and result.live_execution_eligible is False
 assert all(rank is None or rank>=1 for rank in result.rank_by_market.values())
 if scenario.blocked or scenario.unavailable:
  assert result.selected_market is None and result.tie_state=='ALL_INELIGIBLE'


@pytest.mark.parametrize('winner',CANONICAL_MARKET_IDENTITIES)
@pytest.mark.parametrize('direction',(STRONG_BULLISH,STRONG_BEARISH),ids=lambda scenario:scenario.scenario_name)
def test_each_market_can_be_a_deterministic_directional_winner(winner,direction):
 scenarios={identity:direction for identity in CANONICAL_MARKET_IDENTITIES}
 candidates=list(build_four_market_candidate_set(scenarios))
 winner_index=CANONICAL_MARKET_IDENTITIES.index(winner)
 from dataclasses import replace
 candidates[winner_index]=replace(candidates[winner_index],opportunity_confidence=.95)
 from services.opportunity_ranking import rank_four_market_opportunities
 result=rank_four_market_opportunities(tuple(candidates))
 assert result.selected_market==winner and result.rank_by_market[winner]==1
 assert result.selection_confidence==result.score_by_market[winner]

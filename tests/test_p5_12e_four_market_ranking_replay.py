from dataclasses import replace

import pytest

from services.opportunity_ranking import rank_four_market_opportunities
from tests.fixtures.p5_12 import *


def _matrix(scenario=STRONG_BULLISH):return {identity:scenario for identity in CANONICAL_MARKET_IDENTITIES}
def _strongest_valid_score(candidate):
    values={}
    if candidate.trade_opportunity_available:values['opportunity_confidence']=.99
    if candidate.option_chain_available:values['option_chain_confirmation_score']=.99
    if candidate.broader_market_available:values['broader_market_confirmation_score']=.99
    if candidate.external_context_available:values['external_context_confirmation_score']=.99
    if candidate.liquidity_available:values['liquidity_score']=.99
    if candidate.execution_quality_available:values['execution_quality_score']=.99
    return replace(candidate,**values)
def _assert_result(result):
    assert tuple((candidate.underlying_symbol,candidate.exchange) for candidate in result.candidates)==CANONICAL_MARKET_IDENTITIES
    ordered=tuple((candidate.underlying_symbol,candidate.exchange) for candidate in result.ordered_candidates)
    assert tuple(result.rank_by_market[identity] for identity in ordered)==tuple(range(1,len(ordered)+1))
    if result.selected_market is not None:assert result.rank_by_market[result.selected_market]==1 and result.selection_confidence==result.score_by_market[result.selected_market]
    assert result.execution_mode=='PAPER' and result.live_execution_eligible is False


@pytest.mark.parametrize('winner',CANONICAL_MARKET_IDENTITIES)
@pytest.mark.parametrize('scenario',(STRONG_BULLISH,STRONG_BEARISH))
def test_every_market_wins_clean_valid_replay(winner,scenario):
    candidates=list(build_four_market_candidate_set(_matrix(scenario)));index=CANONICAL_MARKET_IDENTITIES.index(winner)
    candidates[index]=replace(candidates[index],opportunity_confidence=.95)
    result=rank_four_market_opportunities(tuple(reversed(candidates)))
    _assert_result(result);assert result.selected_market==winner and result.score_by_market[winner]>max(value for identity,value in result.score_by_market.items() if identity!=winner)


@pytest.mark.parametrize('scenario,event_profiles,session_profiles',(
 (BLOCKED,None,None),(UNAVAILABLE,None,None),(CONFLICTING,None,None),(STRONG_BULLISH,{CANONICAL_MARKET_IDENTITIES[0]:RBI_BLOCK_EVENT_PROFILE},None),(STRONG_BULLISH,None,{CANONICAL_MARKET_IDENTITIES[0]:HOLIDAY_SESSION}),
))
def test_rejected_candidate_never_wins_and_remains_visible(scenario,event_profiles,session_profiles):
    candidates=list(build_four_market_candidate_set(_matrix(scenario),event_profiles_by_market=event_profiles,session_profiles_by_market=session_profiles));candidates[0]=_strongest_valid_score(candidates[0])
    result=rank_four_market_opportunities(tuple(candidates));_assert_result(result)
    if scenario is CONFLICTING:assert result.conflicting_markets==CANONICAL_MARKET_IDENTITIES and result.selected_market is None
    else:assert result.rank_by_market[CANONICAL_MARKET_IDENTITIES[0]] is None or result.selected_market!=CANONICAL_MARKET_IDENTITIES[0]
    assert type(candidates[0]).__name__=='MarketOpportunityCandidateV1' and candidates[0] in result.candidates


def test_mixed_validity_and_all_ineligible_matrices():
    scenarios={CANONICAL_MARKET_IDENTITIES[0]:STRONG_BULLISH,CANONICAL_MARKET_IDENTITIES[1]:WEAK_BULLISH,CANONICAL_MARKET_IDENTITIES[2]:CONFLICTING,CANONICAL_MARKET_IDENTITIES[3]:BLOCKED}
    result=build_ranked_four_market_result(scenarios);_assert_result(result)
    assert result.selected_market==CANONICAL_MARKET_IDENTITIES[0] and result.rank_by_market[CANONICAL_MARKET_IDENTITIES[2]] is None and result.rank_by_market[CANONICAL_MARKET_IDENTITIES[3]] is None
    unavailable=build_ranked_four_market_result(_matrix(UNAVAILABLE));assert unavailable.tie_state=='ALL_INELIGIBLE' and unavailable.selected_market is None and not unavailable.ordered_candidates

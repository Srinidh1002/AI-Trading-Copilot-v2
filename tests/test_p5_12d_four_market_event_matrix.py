from dataclasses import replace

import pytest

from services.opportunity_ranking import rank_four_market_opportunities
from tests.fixtures.p5_12 import *


def _matrix():return {identity:STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}
def _check(result):
    assert tuple((item.underlying_symbol,item.exchange) for item in result.candidates)==CANONICAL_MARKET_IDENTITIES
    ordered=tuple((item.underlying_symbol,item.exchange) for item in result.ordered_candidates)
    assert tuple(result.rank_by_market[item] for item in ordered)==tuple(range(1,len(ordered)+1))
    if result.selected_market:assert result.rank_by_market[result.selected_market]==1 and result.selection_confidence==result.score_by_market[result.selected_market]


def test_clean_candidate_beats_event_warnings_and_rejected_event_session_cases():
    events={CANONICAL_MARKET_IDENTITIES[1]:CPI_WARNING_EVENT_PROFILE,CANONICAL_MARKET_IDENTITIES[2]:RBI_BLOCK_EVENT_PROFILE,CANONICAL_MARKET_IDENTITIES[3]:WEEKLY_EXPIRY_EVENT_PROFILE}
    result=build_ranked_four_market_result(_matrix(),event_profiles_by_market=events)
    _check(result);assert result.selected_market==CANONICAL_MARKET_IDENTITIES[0] and result.rank_by_market[CANONICAL_MARKET_IDENTITIES[2]] is None


def test_holiday_and_event_session_restrictions_cannot_win_and_all_ineligible_is_preserved():
    sessions={CANONICAL_MARKET_IDENTITIES[0]:HOLIDAY_SESSION}
    result=build_ranked_four_market_result(_matrix(),session_profiles_by_market=sessions)
    assert result.rank_by_market[CANONICAL_MARKET_IDENTITIES[0]] is None and result.selected_market!=CANONICAL_MARKET_IDENTITIES[0]
    all_holiday=build_ranked_four_market_result(_matrix(),session_profiles_by_market={identity:HOLIDAY_SESSION for identity in CANONICAL_MARKET_IDENTITIES})
    assert all_holiday.tie_state=='ALL_INELIGIBLE' and all_holiday.selected_market is None and all(rank is None for rank in all_holiday.rank_by_market.values())


@pytest.mark.parametrize('winner',CANONICAL_MARKET_IDENTITIES)
def test_each_market_can_win_valid_event_matrix(winner):
    candidates=list(build_four_market_candidate_set(_matrix()))
    index=CANONICAL_MARKET_IDENTITIES.index(winner);candidates[index]=replace(candidates[index],opportunity_confidence=.95)
    result=rank_four_market_opportunities(tuple(reversed(candidates)))
    forward=rank_four_market_opportunities(tuple(candidates))
    _check(result);assert result.selected_market==winner and result.rank_by_market[winner]==1
    assert all(result.eligibility_by_market[identity]=='ELIGIBLE' for identity in CANONICAL_MARKET_IDENTITIES)
    assert result.score_by_market[winner]>max(score for identity,score in result.score_by_market.items() if identity!=winner)
    assert result.selection_confidence==result.score_by_market[winner] and result.semantic_dict()==forward.semantic_dict()

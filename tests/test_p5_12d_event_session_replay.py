import pytest

from services.contracts.event_risk_context_result_v1 import EventRiskContextResultV1
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.scheduled_market_event_v1 import ScheduledMarketEventV1
from services.opportunity_ranking import evaluate_candidate_eligibility, score_market_opportunity_candidate
from tests.fixtures.p5_12 import *


_CASES=(
 ('rbi',RBI_BLOCK_EVENT_PROFILE,REGULAR_SESSION),('budget',UNION_BUDGET_EVENT_PROFILE,REGULAR_SESSION),('cpi',CPI_WARNING_EVENT_PROFILE,REGULAR_SESSION),('election',ELECTION_EVENT_PROFILE,REGULAR_SESSION),('holiday',NONE,HOLIDAY_SESSION),('special',NONE,SPECIAL_SESSION_PROFILE),('weekly',WEEKLY_EXPIRY_EVENT_PROFILE,WEEKLY_EXPIRY_SESSION),('monthly',MONTHLY_EXPIRY_EVENT_PROFILE,MONTHLY_EXPIRY_SESSION),('rollover',ROLLOVER_EVENT_PROFILE,REGULAR_SESSION),('overlap',OVERLAPPING_EVENTS_PROFILE,REGULAR_SESSION),('event_session',CPI_WARNING_EVENT_PROFILE,HOLIDAY_SESSION),
)


@pytest.mark.parametrize('name,event,session',_CASES,ids=[item[0] for item in _CASES])
@pytest.mark.parametrize('identity',CANONICAL_MARKET_IDENTITIES,ids=lambda value:f'{value[0]}-{value[1]}')
def test_event_session_full_stack_replay_is_typed_deterministic_and_paper_only(name,event,session,identity):
    candidate=build_market_opportunity_candidate(identity,STRONG_BULLISH,event_profile=event,session_profile=session)
    context=candidate.external_market_context;validation=candidate.market_session_validation
    assert type(context) is ExternalMarketContextResultV1 and type(validation) is MarketSessionValidationV1
    assert (candidate.underlying_symbol,candidate.exchange)==(context.underlying_symbol,context.exchange)==(validation.symbol,validation.exchange)==identity
    assert validation.evaluated_at==validation.market_timestamp==REPLAY_EVALUATED_AT
    assert candidate.execution_mode=='PAPER' and candidate.live_execution_eligible is False and candidate.market_regime.execution_mode=='PAPER'
    assert validation.schema_version=='market_session_validation.v1' and validation.to_json()==validation.to_json()
    if event.events:
        assert type(context.event_context) is EventRiskContextResultV1
        assert all(type(item) is ScheduledMarketEventV1 for item in context.event_context.events)
        assert context.event_context.to_json()==context.event_context.to_json()
    assert candidate.to_json()==candidate.to_json()


def test_rbi_cpi_holiday_and_special_session_semantics_are_distinct():
    identity=CANONICAL_MARKET_IDENTITIES[0]
    rbi=build_market_opportunity_candidate(identity,STRONG_BULLISH,event_profile=RBI_BLOCK_EVENT_PROFILE)
    cpi=build_market_opportunity_candidate(identity,STRONG_BULLISH,event_profile=CPI_WARNING_EVENT_PROFILE)
    holiday=build_market_opportunity_candidate(identity,STRONG_BULLISH,session_profile=HOLIDAY_SESSION)
    special=build_market_opportunity_candidate(identity,STRONG_BULLISH,session_profile=SPECIAL_SESSION_PROFILE)
    assert rbi.candidate_status=='BLOCKED' and rbi.entry_restriction_state=='BLOCKED' and not evaluate_candidate_eligibility(rbi).rankable
    assert cpi.candidate_status=='READY_WITH_WARNINGS' and cpi.blockers==() and evaluate_candidate_eligibility(cpi).rankable
    assert holiday.market_session_validation.trading_day_status=='HOLIDAY' and holiday.market_session_validation.paper_execution_allowed is False and not evaluate_candidate_eligibility(holiday).rankable
    assert special.market_session_validation.session_state=='SPECIAL' and special.market_session_validation.trading_day_status=='SPECIAL_TRADING_DAY'


def test_warning_event_score_uses_one_event_risk_penalty_where_rankable():
    candidate=build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[0],STRONG_BULLISH,event_profile=CPI_WARNING_EVENT_PROFILE)
    score=score_market_opportunity_candidate(candidate,evaluate_candidate_eligibility(candidate))
    assert list(score.applied_penalties).count('EVENT_RISK')<=1
    assert 'STALE_DATA' not in score.applied_penalties and 'MISSING_OPTIONAL_EVIDENCE' not in score.applied_penalties

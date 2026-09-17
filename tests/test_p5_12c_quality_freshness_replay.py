from datetime import timedelta

import pytest

from services.contracts.market_opportunity_candidate_v1 import MarketOpportunityCandidateV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.option_chain_intelligence_result_v1 import OptionChainIntelligenceResultV1
from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
from services.opportunity_ranking import evaluate_candidate_eligibility, score_market_opportunity_candidate
from tests.fixtures.p5_12 import *


_FAMILIES = (
    ('fresh', STRONG_BULLISH, None),
    ('delayed', DELAYED, None),
    ('stale', STALE, None),
    ('future', FUTURE, None),
    ('mixed', MIXED_TIMESTAMPS, None),
    ('partial', STRONG_BULLISH, PARTIAL_OPTIONAL_PROFILE),
    ('missing_optional', STRONG_BULLISH, MISSING_OPTIONAL_PROFILE),
    ('provider_blocked_optional', STRONG_BULLISH, OPTIONAL_PROVIDER_BLOCKED_PROFILE),
)


@pytest.mark.parametrize('name,scenario,quality', _FAMILIES, ids=[item[0] for item in _FAMILIES])
@pytest.mark.parametrize('identity', CANONICAL_MARKET_IDENTITIES, ids=lambda item: f'{item[0]}-{item[1]}')
def test_full_stack_quality_freshness_replay_cases_are_typed_and_paper_only(name, scenario, quality, identity):
    candidate = build_market_opportunity_candidate(identity, scenario, component_quality_profile=quality)
    assert type(candidate) is MarketOpportunityCandidateV1
    assert (candidate.underlying_symbol, candidate.exchange) == identity
    assert candidate.evaluated_at == REPLAY_EVALUATED_AT
    assert candidate.execution_mode == 'PAPER' and candidate.live_execution_eligible is False
    assert candidate.market_regime.execution_mode == 'PAPER'
    session = candidate.market_session_validation
    assert type(session) is MarketSessionValidationV1
    assert (session.symbol, session.exchange) == identity
    assert session.evaluated_at == REPLAY_EVALUATED_AT and session.market_timestamp == REPLAY_EVALUATED_AT
    assert session.session_state == 'REGULAR' and session.session_phase == 'REGULAR_TRADING'
    assert session.trading_day_status == 'TRADING_DAY' and session.schema_version == 'market_session_validation.v1'
    assert not candidate.analysis_allowed or session.analysis_allowed
    assert not candidate.new_entries_allowed or session.paper_execution_allowed
    assert session.to_json() == session.to_json()
    assert dict(candidate.source_timestamps) == dict(candidate.source_timestamps)
    assert candidate.to_json() == candidate.to_json()
    assert candidate.metadata == {}


def test_fresh_and_delayed_fixture_classification_is_distinct_from_production_eligibility():
    identity = CANONICAL_MARKET_IDENTITIES[0]
    fresh = build_freshness_timestamp_profile('FRESH')
    delayed = build_freshness_timestamp_profile('DELAYED')
    fresh_profile = classify_fixture_freshness_profile(fresh)
    delayed_profile = classify_fixture_freshness_profile(delayed)
    fresh_candidate = build_market_opportunity_candidate(identity, STRONG_BULLISH)
    delayed_candidate = build_market_opportunity_candidate(identity, DELAYED)
    assert set(fresh_profile.classifications.values()) == {'FRESH', 'UNAVAILABLE'}
    assert 'STALE' not in delayed_profile.classifications.values()
    assert 'FUTURE' not in delayed_profile.classifications.values()
    assert fresh_candidate.candidate_status == 'READY' and not fresh_candidate.warnings
    assert delayed_candidate.freshness_state == 'FRESH' and delayed_candidate.warnings
    assert evaluate_candidate_eligibility(fresh_candidate).rankable
    delayed_score = score_market_opportunity_candidate(delayed_candidate, evaluate_candidate_eligibility(delayed_candidate))
    assert 'STALE_DATA' not in delayed_score.applied_penalties
    assert list(delayed_score.applied_penalties).count('WARNING') <= 1


def test_optional_and_required_stale_future_profiles_have_distinct_candidate_outcomes():
    identity = CANONICAL_MARKET_IDENTITIES[0]
    optional_stale = dict(build_freshness_timestamp_profile('FRESH'))
    optional_stale['broader_market'] = REPLAY_EVALUATED_AT - timedelta(seconds=301)
    stale_profile = classify_fixture_freshness_profile(optional_stale)
    stale_candidate = build_market_opportunity_candidate(identity, STRONG_BULLISH, source_timestamps=optional_stale, component_freshness_profile=stale_profile)
    assert stale_profile.classifications['broader_market'] == 'STALE'
    assert stale_candidate.candidate_status == 'READY_WITH_WARNINGS' and stale_candidate.blockers == ()
    stale_score = score_market_opportunity_candidate(stale_candidate, evaluate_candidate_eligibility(stale_candidate))
    assert list(stale_score.applied_penalties).count('STALE_DATA') == 1
    optional_future = dict(build_freshness_timestamp_profile('FRESH'))
    optional_future['external_context'] = REPLAY_EVALUATED_AT + timedelta(seconds=6)
    future_profile = classify_fixture_freshness_profile(optional_future)
    future_candidate = build_market_opportunity_candidate(identity, STRONG_BULLISH, source_timestamps=optional_future, component_freshness_profile=future_profile)
    assert future_profile.classifications['external_context'] == 'FUTURE'
    assert future_candidate.freshness_state == 'FUTURE' and future_candidate.candidate_status == 'READY_WITH_WARNINGS'
    assert 'STALE_DATA' not in score_market_opportunity_candidate(future_candidate, evaluate_candidate_eligibility(future_candidate)).applied_penalties
    required = dict(build_freshness_timestamp_profile('FRESH'))
    required['market_regime'] = REPLAY_EVALUATED_AT + timedelta(seconds=6)
    required_profile = classify_fixture_freshness_profile(required)
    blocked = build_market_opportunity_candidate(identity, STRONG_BULLISH, source_timestamps=required, component_freshness_profile=required_profile)
    assert required_profile.required_failures == ('market_regime',)
    assert blocked.candidate_status == 'BLOCKED' and blocked.entry_restriction_state == 'BLOCKED'
    assert not evaluate_candidate_eligibility(blocked).rankable


def test_partial_typed_evidence_and_fixture_owned_liquidity_execution_provenance():
    identity = CANONICAL_MARKET_IDENTITIES[0]
    option = build_option_chain_intelligence(identity, STRONG_BULLISH, quality_state='PRESENT_PARTIAL')
    broader = build_broader_market_intelligence(identity, STRONG_BULLISH, quality_state='PRESENT_PARTIAL')
    external = build_external_context(identity, STRONG_BULLISH, quality_state='PRESENT_PARTIAL')
    assert type(option) is OptionChainIntelligenceResultV1 and option.intelligence_status == 'READY_WITH_WARNINGS'
    assert type(broader) is BroaderMarketIntelligenceResultV1 and broader.breadth_evidence is not None
    assert type(external) is ExternalMarketContextResultV1 and external.context_status == 'READY_WITH_WARNINGS'
    timestamps = dict(build_freshness_timestamp_profile('FRESH'))
    timestamps.update(liquidity=REPLAY_EVALUATED_AT, execution_quality=REPLAY_EVALUATED_AT)
    fixture_profile = classify_fixture_freshness_profile(timestamps)
    candidate = build_market_opportunity_candidate(identity, STRONG_BULLISH, source_timestamps=timestamps, component_freshness_profile=fixture_profile, component_quality_profile=PARTIAL_OPTIONAL_PROFILE)
    assert candidate.option_chain_available and candidate.option_chain_confirmation_score > 0.0
    assert candidate.option_chain_confirmation_score < build_market_opportunity_candidate(identity, STRONG_BULLISH).option_chain_confirmation_score
    assert fixture_profile.source_timestamps['liquidity'] == REPLAY_EVALUATED_AT

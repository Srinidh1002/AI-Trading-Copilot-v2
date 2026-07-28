from services.contracts.market_opportunity_candidate_v1 import MarketOpportunityCandidateV1
from services.contracts.trade_opportunity_v1 import TradeOpportunityV1
from services.opportunity_ranking.eligibility import evaluate_candidate_eligibility
from datetime import timedelta
from tests.fixtures.p5_12 import *
def test_typed_fixture_stack_and_canonical_candidate_set():
 scenarios={identity:STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}
 for identity in CANONICAL_MARKET_IDENTITIES:
  technical=build_technical_intelligence(identity,STRONG_BULLISH); option=build_option_chain_intelligence(identity,STRONG_BULLISH); regime=build_market_regime(identity,STRONG_BULLISH,technical=technical,option_chain=option); opportunity=build_trade_opportunity(identity,STRONG_BULLISH,market_regime=regime,option_chain=option)
  assert (technical.underlying_symbol,technical.exchange)==identity and (option.underlying_symbol,option.exchange)==identity and type(opportunity) is TradeOpportunityV1
 candidates=build_four_market_candidate_set(scenarios)
 assert all(type(candidate) is MarketOpportunityCandidateV1 for candidate in candidates)
 assert tuple((candidate.underlying_symbol,candidate.exchange) for candidate in candidates)==CANONICAL_MARKET_IDENTITIES


def test_all_scenario_families_construct_available_or_explicitly_restricted_layers():
 scenarios=(STRONG_BULLISH,STRONG_BEARISH,WEAK_BULLISH,WEAK_BEARISH,RANGE_BOUND,HIGH_VOLATILITY,CONFLICTING,BLOCKED,UNAVAILABLE)
 identity=CANONICAL_MARKET_IDENTITIES[0]
 for scenario in scenarios:
  broader=build_broader_market_intelligence(identity,scenario); external=build_external_context(identity,scenario); regime=build_market_regime(identity,scenario); candidate=build_market_opportunity_candidate(identity,scenario,broader_market=broader,external_context=external,market_regime=regime)
  assert (broader.underlying_symbol,broader.exchange)==identity and (external.underlying_symbol,external.exchange)==identity
  assert candidate.execution_mode=='PAPER' and candidate.live_execution_eligible is False
  if scenario.unavailable:
   assert candidate.candidate_status=='UNAVAILABLE' and candidate.opportunity_confidence==0.0 and not candidate.new_entries_allowed
  if scenario.blocked:assert candidate.candidate_status=='BLOCKED' and candidate.blockers
  if scenario.conflicting:assert candidate.candidate_status=='CONFLICTING' and candidate.contradictions
  if scenario.conflicting:
   assert broader.intelligence_status=='CONFLICTING' and broader.confirmation_state=='PARTIAL'
   assert broader.divergence_state=='DIRECTIONAL_DIVERGENCE' and broader.contradictions
   assert broader.to_dict()==broader.to_dict()


def test_public_fixture_api_propagates_quality_and_freshness_provenance():
 identity=CANONICAL_MARKET_IDENTITIES[0]; stale=dict(build_freshness_timestamp_profile('STALE'))
 technical=build_technical_intelligence(identity,STALE,source_timestamp=stale['technical'])
 option=build_option_chain_intelligence(identity,STALE,source_timestamp=stale['option_chain'])
 broader=build_broader_market_intelligence(identity,STALE,source_timestamp=stale['broader_market'])
 external=build_external_context(identity,STALE,source_timestamp=stale['external_context'])
 assert technical.created_at==stale['technical'] and option.created_at==stale['option_chain']
 assert broader.created_at==stale['broader_market'] and external.created_at==stale['external_context']
 candidate=build_market_opportunity_candidate(identity,STALE,source_timestamps=stale)
 assert dict(candidate.source_timestamps)==dict(to_candidate_source_timestamps(stale)) and candidate.freshness_state=='STALE' and candidate.warnings
 assert candidate.candidate_status=='READY_WITH_WARNINGS' and candidate.to_json()==candidate.to_json()
 assert stale==dict(build_freshness_timestamp_profile('STALE'))
 delayed=build_market_opportunity_candidate(identity,DELAYED)
 future=build_market_opportunity_candidate(identity,FUTURE)
 mixed=build_market_opportunity_candidate(identity,MIXED_TIMESTAMPS)
 assert delayed.freshness_state=='FRESH' and delayed.warnings
 assert future.freshness_state=='FUTURE' and future.warnings
 assert mixed.freshness_state=='MIXED' and len(set(mixed.source_timestamps.values())) > 1
 partial=build_market_opportunity_candidate(identity,PARTIAL_OPTIONAL)
 assert not partial.option_chain_available and partial.option_chain_confirmation_score==0.0
 missing=describe_missing_required_components(MISSING_REQUIRED)
 assert missing['fails_closed'] and missing['missing_required_components']==('TECHNICAL',)
 blocked=build_market_opportunity_candidate(identity,PROVIDER_BLOCKED)
 assert blocked.candidate_status=='BLOCKED' and blocked.blockers==('P512_PROVIDER_BLOCKED',)


def test_four_market_helpers_accept_independent_provenance_profiles():
 scenarios={identity:STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}
 profiles={identity:build_freshness_timestamp_profile('FRESH' if index % 2 == 0 else 'DELAYED') for index,identity in enumerate(CANONICAL_MARKET_IDENTITIES)}
 candidates=build_four_market_candidate_set(scenarios,source_timestamps_by_market=profiles)
 assert tuple(dict(candidate.source_timestamps) for candidate in candidates)==tuple(dict(to_candidate_source_timestamps(profiles[identity])) for identity in CANONICAL_MARKET_IDENTITIES)
 ranked=build_ranked_four_market_result(scenarios,source_timestamps_by_market=profiles)
 assert tuple((candidate.underlying_symbol,candidate.exchange) for candidate in ranked.candidates)==CANONICAL_MARKET_IDENTITIES
 ordered_identities=tuple((candidate.underlying_symbol,candidate.exchange) for candidate in ranked.ordered_candidates)
 assert tuple(ranked.rank_by_market[identity] for identity in ordered_identities)==tuple(range(1,len(ordered_identities)+1))
 assert all(ranked.eligibility_by_market[identity] not in {'BLOCKED','UNAVAILABLE'} for identity in ordered_identities)
 assert all(identity not in ordered_identities for identity,rank in ranked.rank_by_market.items() if rank is None)
 if ranked.selected_market is not None:assert ranked.selected_market==ordered_identities[0]
 all_blocked=build_ranked_four_market_result({identity:BLOCKED for identity in CANONICAL_MARKET_IDENTITIES})
 assert all(candidate.candidate_status=='BLOCKED' for candidate in all_blocked.candidates)


def test_fresh_directional_defaults_remain_rankable():
 for scenario in (STRONG_BULLISH,STRONG_BEARISH):
  candidate=build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[0],scenario)
  eligibility=evaluate_candidate_eligibility(candidate)
  assert candidate.candidate_status=='READY' and not candidate.warnings and not candidate.blockers and not candidate.contradictions
  assert eligibility.rankable and eligibility.freshness_failure=='NONE'
  assert not eligibility.failed_thresholds and not eligibility.blockers
  ranked=build_ranked_four_market_result({identity:scenario for identity in CANONICAL_MARKET_IDENTITIES})
  assert ranked.selected_market is not None


def test_quality_and_freshness_profiles_supply_safe_replay_seams():
 identity=CANONICAL_MARKET_IDENTITIES[0];timestamps=dict(build_freshness_timestamp_profile('FRESH'))
 timestamps['broader_market']=REPLAY_EVALUATED_AT-timedelta(seconds=301)
 optional=classify_fixture_freshness_profile(timestamps)
 candidate=build_market_opportunity_candidate(identity,STRONG_BULLISH,source_timestamps=timestamps,component_freshness_profile=optional)
 assert optional.classifications['broader_market']=='STALE' and not optional.required_failures
 assert candidate.freshness_state=='STALE' and evaluate_candidate_eligibility(candidate).rankable
 timestamps['market_regime']=REPLAY_EVALUATED_AT+timedelta(seconds=6)
 required=classify_fixture_freshness_profile(timestamps)
 blocked=build_market_opportunity_candidate(identity,STRONG_BULLISH,source_timestamps=timestamps,component_freshness_profile=required)
 assert required.required_failures==('market_regime',) and blocked.candidate_status=='BLOCKED' and blocked.blockers
 option=build_option_chain_intelligence(identity,STRONG_BULLISH,quality_state='PRESENT_PARTIAL')
 broader=build_broader_market_intelligence(identity,STRONG_BULLISH,quality_state='PRESENT_PARTIAL')
 external=build_external_context(identity,STRONG_BULLISH,quality_state='PRESENT_PARTIAL')
 assert option.intelligence_status=='READY_WITH_WARNINGS' and broader.breadth_evidence is not None and external.context_status=='READY_WITH_WARNINGS'
 partial=build_market_opportunity_candidate(identity,STRONG_BULLISH,component_quality_profile=PARTIAL_OPTIONAL_PROFILE)
 assert partial.option_chain_available and partial.option_chain_confirmation_score<.8
 optional_blocked=build_market_opportunity_candidate(identity,STRONG_BULLISH,component_quality_profile=OPTIONAL_PROVIDER_BLOCKED_PROFILE)
 assert optional_blocked.candidate_status=='READY_WITH_WARNINGS' and optional_blocked.blockers==() and optional_blocked.warnings
 assert not optional_blocked.external_context_available and optional_blocked.external_context_confirmation_score==0.0 and evaluate_candidate_eligibility(optional_blocked).rankable
 required_blocked=build_market_opportunity_candidate(identity,STRONG_BULLISH,component_quality_profile=REQUIRED_PROVIDER_BLOCKED_PROFILE)
 assert required_blocked.candidate_status=='BLOCKED' and required_blocked.blockers and not evaluate_candidate_eligibility(required_blocked).rankable
 case=build_missing_required_evaluation_case(identity,STRONG_BULLISH)
 assert case.evaluator_result_kwargs()['missing_required_reference'] is True


def test_four_market_quality_and_freshness_profiles_are_independent():
 scenarios={identity:STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}
 freshness={identity:classify_fixture_freshness_profile(build_freshness_timestamp_profile('FRESH')) for identity in CANONICAL_MARKET_IDENTITIES}
 quality={CANONICAL_MARKET_IDENTITIES[1]:PARTIAL_OPTIONAL_PROFILE}
 candidates=build_four_market_candidate_set(scenarios,component_quality_profiles_by_market=quality,component_freshness_profiles_by_market=freshness)
 assert candidates[1].option_chain_confirmation_score<candidates[0].option_chain_confirmation_score


def test_event_and_session_replay_seams_are_typed_and_distinct():
 identity=CANONICAL_MARKET_IDENTITIES[0]
 for profile in (RBI_BLOCK_EVENT_PROFILE,UNION_BUDGET_EVENT_PROFILE,CPI_WARNING_EVENT_PROFILE,ELECTION_EVENT_PROFILE,WEEKLY_EXPIRY_EVENT_PROFILE,MONTHLY_EXPIRY_EVENT_PROFILE,ROLLOVER_EVENT_PROFILE,OVERLAPPING_EVENTS_PROFILE):
  context=build_external_context(identity,STRONG_BULLISH,event_profile=profile)
  assert context.event_context is not None and context.event_context.events
 rbi=build_market_opportunity_candidate(identity,STRONG_BULLISH,event_profile=RBI_BLOCK_EVENT_PROFILE)
 cpi=build_market_opportunity_candidate(identity,STRONG_BULLISH,event_profile=CPI_WARNING_EVENT_PROFILE)
 holiday=build_market_opportunity_candidate(identity,STRONG_BULLISH,session_profile=HOLIDAY_SESSION)
 special=build_market_session_validation(identity,session_profile=SPECIAL_SESSION_PROFILE)
 assert rbi.candidate_status=='BLOCKED' and rbi.blockers
 assert cpi.candidate_status=='READY_WITH_WARNINGS' and cpi.warnings and evaluate_candidate_eligibility(cpi).rankable
 assert holiday.candidate_status=='BLOCKED' and holiday.market_session_validation.trading_day_status=='HOLIDAY'
 assert special.session_state=='SPECIAL' and special.special_session
 assert WEEKLY_EXPIRY_EVENT_PROFILE.events[0][0]!=MONTHLY_EXPIRY_EVENT_PROFILE.events[0][0]


def test_four_market_event_session_profiles_are_independent():
 scenarios={identity:STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}
 events={CANONICAL_MARKET_IDENTITIES[1]:CPI_WARNING_EVENT_PROFILE,CANONICAL_MARKET_IDENTITIES[2]:RBI_BLOCK_EVENT_PROFILE}
 sessions={CANONICAL_MARKET_IDENTITIES[3]:HOLIDAY_SESSION}
 result=build_ranked_four_market_result(scenarios,event_profiles_by_market=events,session_profiles_by_market=sessions)
 assert result.selected_market==CANONICAL_MARKET_IDENTITIES[0] and result.rank_by_market[CANONICAL_MARKET_IDENTITIES[2]] is None and result.rank_by_market[CANONICAL_MARKET_IDENTITIES[3]] is None

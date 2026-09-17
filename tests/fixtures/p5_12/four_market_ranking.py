from services.contracts.four_market_ranking_policy_v1 import DEFAULT_FOUR_MARKET_RANKING_POLICY
from services.contracts.market_opportunity_candidate_v1 import MarketOpportunityCandidateV1
from services.opportunity_ranking import rank_four_market_opportunities
from tests.fixtures.p5_10j_market_regime_replay import input_for
from .identities import CANONICAL_MARKET_IDENTITIES,normalize_test_identity
from .market_regime import build_market_regime
from .trade_opportunity import build_trade_opportunity
from .broader_market import build_broader_market_intelligence
from .external_context import build_external_context
from .scenarios import MissingRequiredEvaluationCaseV1
from .timebase import REPLAY_EVALUATED_AT,build_freshness_timestamp_profile,to_candidate_source_timestamps,classify_fixture_freshness_profile
from .event_session import NONE,REGULAR_SESSION,build_market_session_validation
def build_market_opportunity_candidate(identity,scenario,*,technical=None,option_chain=None,broader_market=None,external_context=None,market_regime=None,trade_opportunity=None,evaluated_at=REPLAY_EVALUATED_AT,source_timestamps=None,component_quality_profile=None,component_freshness_profile=None,optional_component_states=None,liquidity_timestamp=None,execution_quality_timestamp=None,event_profile=None,event_profiles=None,session_profile=None,market_session_validation=None,overrides=None):
 symbol,exchange=normalize_test_identity(*identity); inp=input_for((symbol,exchange),identifier=f'p512-input-{scenario.scenario_name}-{symbol}')
 profile=dict(source_timestamps) if source_timestamps is not None else dict(build_freshness_timestamp_profile('MIXED' if scenario.freshness_state=='MIXED' else scenario.freshness_state if scenario.freshness_state in {'FRESH','DELAYED','STALE','FUTURE','UNAVAILABLE'} else 'FRESH',evaluated_at=evaluated_at))
 if liquidity_timestamp is not None:profile['liquidity']=liquidity_timestamp
 if execution_quality_timestamp is not None:profile['execution_quality']=execution_quality_timestamp
 freshness_profile=component_freshness_profile or classify_fixture_freshness_profile(profile,evaluated_at=evaluated_at)
 quality=component_quality_profile
 quality_state=lambda component:getattr(quality,component,'PRESENT_GOOD') if quality is not None else 'PRESENT_GOOD'
 event_value=event_profile or NONE;session_value=market_session_validation or build_market_session_validation((symbol,exchange),session_profile=session_profile or REGULAR_SESSION,evaluated_at=evaluated_at)
 regime=market_regime or build_market_regime((symbol,exchange),scenario,evaluated_at=evaluated_at,source_timestamps=profile,event_profile=event_value,event_profiles=event_profiles,session_profile=session_profile,market_session_validation=session_value)
 if broader_market is None and not scenario.unavailable:broader_market=build_broader_market_intelligence((symbol,exchange),scenario,evaluated_at=evaluated_at,source_timestamp=profile.get('broader_market'),quality_state=quality_state('broader_market'))
 if external_context is None and not scenario.unavailable:external_context=build_external_context((symbol,exchange),scenario,evaluated_at=evaluated_at,source_timestamp=profile.get('external_context'),quality_state=quality_state('external_context'),event_profile=event_value,event_profiles=event_profiles)
 opportunity=trade_opportunity or build_trade_opportunity((symbol,exchange),scenario,market_regime=regime,option_chain=option_chain,evaluated_at=evaluated_at,source_timestamp=profile.get('trade_opportunity'))
 freshness=freshness_profile.freshness_state if component_freshness_profile is not None or source_timestamps is not None or liquidity_timestamp is not None or execution_quality_timestamp is not None else 'MIXED' if scenario.freshness_state=='MIXED' else 'FUTURE' if scenario.freshness_state=='FUTURE' else 'STALE' if scenario.freshness_state=='STALE' else 'UNAVAILABLE' if scenario.unavailable else 'FRESH'
 timestamps=to_candidate_source_timestamps(profile)
 freshness_warning=freshness in {'STALE','FUTURE','MIXED'} or scenario.freshness_state=='DELAYED'
 values=dict(candidate_id=f'p512-candidate-{scenario.scenario_name}-{symbol}',evaluated_at=evaluated_at,underlying_symbol=symbol,exchange=exchange,market_regime=regime,market_session_validation=session_value,candidate_status='READY_WITH_WARNINGS' if freshness_warning else 'READY',analysis_allowed=session_value.analysis_allowed,new_entries_allowed=session_value.paper_execution_allowed,opportunity_confidence=.8,regime_suitability_score=.8,technical_confirmation_score=.8,option_chain_confirmation_score=.8,broader_market_confirmation_score=.5 if broader_market else 0.,external_context_confirmation_score=.5 if external_context else 0.,data_quality_score=.8,liquidity_score=.8,execution_quality_score=.8,trade_opportunity_available=True,option_chain_available=True,broader_market_available=broader_market is not None,external_context_available=external_context is not None,liquidity_available=True,execution_quality_available=True,entry_restriction_state='OPEN',data_quality_state='GOOD',freshness_state=freshness,trade_opportunity=opportunity,broader_market_intelligence=broader_market,external_market_context=external_context,source_timestamps=timestamps,warnings=('P512_FRESHNESS_WARNING',) if freshness_warning else ())
 profiles=tuple(event_profiles or (event_value,));event_warnings=tuple(item for profile_item in profiles for item in profile_item.warnings);event_blockers=tuple(item for profile_item in profiles for item in profile_item.blockers)
 if event_warnings:values.update(warnings=tuple(dict.fromkeys(values['warnings']+event_warnings)),entry_restriction_state='WARNING')
 if event_blockers:values.update(candidate_status='BLOCKED',new_entries_allowed=False,entry_restriction_state='BLOCKED',blockers=tuple(dict.fromkeys(event_blockers)),warnings=tuple(dict.fromkeys(values['warnings']+event_warnings)))
 if not session_value.paper_execution_allowed:values.update(candidate_status='BLOCKED',new_entries_allowed=False,entry_restriction_state='BLOCKED',blockers=tuple(dict.fromkeys(values.get('blockers',())+session_value.blockers)),warnings=tuple(dict.fromkeys(values['warnings']+session_value.warnings)))
 if scenario.missing_optional_components:
  optional=set(scenario.missing_optional_components)
  if 'OPTION_CHAIN' in optional:values.update(option_chain_available=False,option_chain_confirmation_score=0.)
  if 'BROADER_MARKET' in optional:values.update(broader_market_available=False,broader_market_confirmation_score=0.,broader_market_intelligence=None)
  if 'EXTERNAL_CONTEXT' in optional:values.update(external_context_available=False,external_context_confirmation_score=0.,external_market_context=None)
  if 'TRADE_OPPORTUNITY' in optional:values.update(trade_opportunity_available=False,opportunity_confidence=0.,trade_opportunity=None)
 optional_states=dict(optional_component_states or {})
 for component,state in tuple(optional_states.items())+tuple((component,quality_state(component)) for component in ('option_chain','broader_market','external_context','trade_opportunity','liquidity','execution_quality')):
  if state not in {'MISSING_OPTIONAL','UNAVAILABLE_OPTIONAL','PROVIDER_BLOCKED_OPTIONAL'}:continue
  warning='P512_PROVIDER_BLOCKED_OPTIONAL' if state=='PROVIDER_BLOCKED_OPTIONAL' else 'P512_MISSING_OPTIONAL'
  values['warnings']=tuple(dict.fromkeys(values['warnings']+(warning,)))
  if component=='option_chain':values.update(option_chain_available=False,option_chain_confirmation_score=0.)
  if component=='broader_market':values.update(broader_market_available=False,broader_market_confirmation_score=0.,broader_market_intelligence=None)
  if component=='external_context':values.update(external_context_available=False,external_context_confirmation_score=0.,external_market_context=None)
  if component=='trade_opportunity':values.update(trade_opportunity_available=False,opportunity_confidence=0.,trade_opportunity=None)
  if component=='liquidity':values.update(liquidity_available=False,liquidity_score=0.)
  if component=='execution_quality':values.update(execution_quality_available=False,execution_quality_score=0.)
 for component in ('technical','market_regime'):
  if quality_state(component) in {'MISSING_REQUIRED','UNAVAILABLE_REQUIRED','PROVIDER_BLOCKED_REQUIRED'} or component_freshness_profile is not None and component in freshness_profile.required_failures:
   values.update(candidate_status='BLOCKED',new_entries_allowed=False,entry_restriction_state='BLOCKED',blockers=('P512_REQUIRED_'+component.upper(),),warnings=())
 if quality_state('option_chain') in {'PRESENT_PARTIAL','PRESENT_DEGRADED'}:values['option_chain_confirmation_score']=.4 if quality_state('option_chain')=='PRESENT_PARTIAL' else .3
 if quality_state('broader_market') in {'PRESENT_PARTIAL','PRESENT_DEGRADED'}:values['broader_market_confirmation_score']=.4 if quality_state('broader_market')=='PRESENT_PARTIAL' else .3
 if quality_state('external_context') in {'PRESENT_PARTIAL','PRESENT_DEGRADED'}:values['external_context_confirmation_score']=.4 if quality_state('external_context')=='PRESENT_PARTIAL' else .3
 if scenario.blocked:values.update(candidate_status='BLOCKED',new_entries_allowed=False,entry_restriction_state='BLOCKED',blockers=('P512_PROVIDER_BLOCKED',) if scenario.provider_blocked_components else ('P512_BLOCKED',),warnings=())
 if scenario.conflicting:values.update(candidate_status='CONFLICTING',contradictions=('P512_CONFLICT',))
 if scenario.unavailable:values.update(candidate_status='UNAVAILABLE',new_entries_allowed=False,opportunity_confidence=0.,regime_suitability_score=0.,technical_confirmation_score=0.,option_chain_confirmation_score=0.,broader_market_confirmation_score=0.,external_context_confirmation_score=0.,data_quality_score=0.,liquidity_score=0.,execution_quality_score=0.,trade_opportunity_available=False,option_chain_available=False,broader_market_available=False,external_context_available=False,liquidity_available=False,execution_quality_available=False,trade_opportunity=None,broader_market_intelligence=None,external_market_context=None,data_quality_state='UNAVAILABLE',freshness_state='UNAVAILABLE',entry_restriction_state='UNAVAILABLE',blockers=('P512_UNAVAILABLE',))
 if values['candidate_status']=='READY' and values['warnings']:values['candidate_status']='READY_WITH_WARNINGS'
 values.update(dict(overrides or {}));return MarketOpportunityCandidateV1(**values)
def build_missing_required_evaluation_case(identity,scenario,*,missing_component='MARKET_REGIME'):
 return MissingRequiredEvaluationCaseV1(build_market_opportunity_candidate(identity,scenario),missing_component)
def build_four_market_candidate_set(scenario_by_market,*,evaluated_at=REPLAY_EVALUATED_AT,policy=DEFAULT_FOUR_MARKET_RANKING_POLICY,source_timestamps_by_market=None,component_quality_profiles_by_market=None,component_freshness_profiles_by_market=None,event_profiles_by_market=None,session_profiles_by_market=None):
 return tuple(build_market_opportunity_candidate(identity,scenario_by_market[identity],evaluated_at=evaluated_at,source_timestamps=(source_timestamps_by_market or {}).get(identity),component_quality_profile=(component_quality_profiles_by_market or {}).get(identity),component_freshness_profile=(component_freshness_profiles_by_market or {}).get(identity),event_profile=(event_profiles_by_market or {}).get(identity),session_profile=(session_profiles_by_market or {}).get(identity)) for identity in CANONICAL_MARKET_IDENTITIES)
def build_ranked_four_market_result(scenario_by_market,*,evaluated_at=REPLAY_EVALUATED_AT,policy=DEFAULT_FOUR_MARKET_RANKING_POLICY,source_timestamps_by_market=None,component_quality_profiles_by_market=None,component_freshness_profiles_by_market=None,event_profiles_by_market=None,session_profiles_by_market=None):
 return rank_four_market_opportunities(build_four_market_candidate_set(scenario_by_market,evaluated_at=evaluated_at,policy=policy,source_timestamps_by_market=source_timestamps_by_market,component_quality_profiles_by_market=component_quality_profiles_by_market,component_freshness_profiles_by_market=component_freshness_profiles_by_market,event_profiles_by_market=event_profiles_by_market,session_profiles_by_market=session_profiles_by_market),policy)

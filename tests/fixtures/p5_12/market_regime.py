from services.market_regime import evaluate_market_regime
from tests.fixtures.p5_10j_market_regime_replay import input_for,broader,external,session,technical as technical_component
from .identities import normalize_test_identity
from .timebase import REPLAY_EVALUATED_AT,build_freshness_timestamp_profile
from .event_session import NONE,REGULAR_SESSION,build_market_session_validation
def build_market_regime(identity,scenario,*,technical=None,option_chain=None,broader_market=None,external_context=None,evaluated_at=REPLAY_EVALUATED_AT,source_timestamps=None,event_profile=None,event_profiles=None,session_profile=None,market_session_validation=None,overrides=None):
 symbol,exchange=normalize_test_identity(*identity); identity=(symbol,exchange); timestamps=dict(source_timestamps) if source_timestamps is not None else dict(build_freshness_timestamp_profile(scenario.freshness_state if scenario.freshness_state in {'FRESH','DELAYED','STALE','FUTURE','MIXED','UNAVAILABLE'} else 'FRESH',evaluated_at=evaluated_at)); args={}
 profile=event_profile or NONE;session_value=market_session_validation or build_market_session_validation(identity,session_profile=session_profile or REGULAR_SESSION,evaluated_at=evaluated_at)
 args['session_component']=session_value
 if scenario.unavailable:args['technical_component']=None
 elif scenario.blocked:args['session_component']=session(identity,analysis=False,entries=False,timestamp=timestamps.get('market_regime',evaluated_at))
 elif scenario.conflicting:args['broader_component']=broader(identity,direction='NEGATIVE',confirmation='CONFIRMING',timestamp=timestamps.get('broader_market',evaluated_at))
 elif scenario.direction=='HIGH_VOLATILITY':args['broader_component']=broader(identity,volatility='HIGH',timestamp=timestamps.get('broader_market',evaluated_at))
 elif 'BEARISH' in scenario.direction:args['technical_component']=technical_component(identity,direction='NEGATIVE',timestamp=timestamps.get('technical',evaluated_at))
 else:args['technical_component']=technical_component(identity,timestamp=timestamps.get('technical',evaluated_at))
 if not scenario.unavailable and args.get('broader_component') is None and timestamps.get('broader_market') is not None:args['broader_component']=broader(identity,timestamp=timestamps['broader_market'])
 if not scenario.unavailable and timestamps.get('external_context') is not None:args['external_component']=external(identity,timestamp=timestamps['external_context'])
 if profile.events or event_profiles:
  profiles=tuple(event_profiles or (profile,));blocked=any(item.blocking for item in profiles);warning=any(item.warnings for item in profiles)
  args['external_component']=external(identity,event='EXTREME' if blocked else 'HIGH' if warning else 'NONE',restriction='BLOCKED' if blocked else 'WARNING' if warning else 'OPEN',timestamp=timestamps.get('external_context',evaluated_at))
 result=evaluate_market_regime(input_for(identity,identifier=f'p512-regime-{scenario.scenario_name}-{symbol}',**args))
 if overrides:raise ValueError('market-regime overrides are not supported by the certified aggregate fixture')
 return result

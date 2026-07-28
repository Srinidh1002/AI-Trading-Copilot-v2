from datetime import datetime,timedelta,timezone
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
# Align with the certified P5-10 canonical regime replay input timestamp.
REPLAY_EVALUATED_AT=datetime(2026,1,1,9,15,tzinfo=timezone.utc)
REPLAY_SOURCE_FRESH_AT=REPLAY_EVALUATED_AT
REPLAY_SOURCE_DELAYED_AT=REPLAY_EVALUATED_AT-timedelta(seconds=60)
REPLAY_SOURCE_STALE_AT=REPLAY_EVALUATED_AT-timedelta(seconds=901)
REPLAY_SOURCE_FUTURE_AT=REPLAY_EVALUATED_AT+timedelta(seconds=6)
REPLAY_SOURCE_OLDER_AT=REPLAY_EVALUATED_AT-timedelta(seconds=1800)
REPLAY_SOURCE_MAX_AGE_AT=REPLAY_EVALUATED_AT-timedelta(seconds=300)
REPLAY_SOURCE_FUTURE_TOLERANCE_AT=REPLAY_EVALUATED_AT+timedelta(seconds=5)
REPLAY_SOURCE_FUTURE_BEYOND_AT=REPLAY_EVALUATED_AT+timedelta(seconds=6)
REPLAY_SOURCE_SKEW_BOUNDARY_AT=REPLAY_EVALUATED_AT-timedelta(seconds=900)
REPLAY_SOURCE_SKEW_BEYOND_AT=REPLAY_EVALUATED_AT-timedelta(seconds=901)
def build_source_timestamps(**values):
 defaults={'technical':REPLAY_SOURCE_FRESH_AT,'option_chain':REPLAY_SOURCE_FRESH_AT,'broader_market':REPLAY_SOURCE_FRESH_AT,'external_context':REPLAY_SOURCE_FRESH_AT,'market_regime':REPLAY_SOURCE_FRESH_AT,'trade_opportunity':REPLAY_SOURCE_FRESH_AT}
 defaults.update(values)
 return MappingProxyType(dict(sorted(defaults.items())))
def build_freshness_timestamp_profile(freshness_state,*,evaluated_at=REPLAY_EVALUATED_AT):
 state=freshness_state.upper();fresh=evaluated_at;delayed=evaluated_at-timedelta(seconds=60);stale=evaluated_at-timedelta(seconds=901);future=evaluated_at+timedelta(seconds=6)
 if state=='FRESH':values={key:fresh for key in ('technical','option_chain','broader_market','external_context','market_regime','trade_opportunity')}
 elif state=='DELAYED':values={key:delayed for key in ('technical','option_chain','broader_market','external_context','market_regime','trade_opportunity')}
 elif state=='STALE':values={key:stale for key in ('technical','option_chain','broader_market','external_context','market_regime','trade_opportunity')}
 elif state=='FUTURE':values={key:future for key in ('technical','option_chain','broader_market','external_context','market_regime','trade_opportunity')}
 elif state=='MIXED':values={'technical':fresh,'option_chain':delayed,'broader_market':stale,'external_context':future,'market_regime':fresh,'trade_opportunity':fresh}
 elif state=='UNAVAILABLE':values={}
 else:raise ValueError('freshness_state')
 return MappingProxyType(dict(sorted(values.items())))

def to_candidate_source_timestamps(source_timestamps):
 """Convert documented lowercase fixture keys to candidate-contract keys."""
 if not isinstance(source_timestamps,Mapping):raise TypeError('source_timestamps')
 return MappingProxyType(dict(sorted((key.upper(),value) for key,value in source_timestamps.items())))

@dataclass(frozen=True)
class ComponentFreshnessProfileV1:
 source_timestamps:MappingProxyType;classifications:MappingProxyType;freshness_state:str;required_failures:tuple[str,...];optional_warnings:tuple[str,...];skew_diagnostic:str

def classify_fixture_freshness_profile(source_timestamps,*,evaluated_at=REPLAY_EVALUATED_AT,required_components=('technical','market_regime'),optional_components=('option_chain','broader_market','external_context','trade_opportunity','liquidity','execution_quality')):
 if not isinstance(source_timestamps,Mapping):raise TypeError('source_timestamps')
 values=dict(source_timestamps);components=tuple(dict.fromkeys(required_components+optional_components));states={};ages=[]
 for component in components:
  timestamp=values.get(component)
  if timestamp is None:states[component]='UNAVAILABLE';continue
  delta=(evaluated_at-timestamp).total_seconds();ages.append(timestamp)
  states[component]='FUTURE' if delta < -5 else 'STALE' if delta > 300 else 'DELAYED' if delta > 0 else 'FRESH'
 required=tuple(component for component in required_components if states.get(component) in {'STALE','FUTURE','UNAVAILABLE'})
 optional=tuple(component for component in optional_components if states.get(component) in {'STALE','FUTURE','UNAVAILABLE'})
 skew='SKEW' if ages and (max(ages)-min(ages)).total_seconds()>900 else 'NONE'
 present=set(states.values())
 aggregate='UNAVAILABLE' if 'UNAVAILABLE' in (states.get(component) for component in required_components) else 'MIXED' if skew=='SKEW' else 'FUTURE' if 'FUTURE' in present else 'STALE' if 'STALE' in present else 'FRESH'
 return ComponentFreshnessProfileV1(MappingProxyType(dict(sorted(values.items()))),MappingProxyType(dict(sorted(states.items()))),aggregate,required,optional,skew)

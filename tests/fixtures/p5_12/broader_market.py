from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.market_breadth_evidence_v1 import MarketBreadthEvidenceV1
from .identities import normalize_test_identity
from .timebase import REPLAY_EVALUATED_AT,build_source_timestamps
def build_broader_market_intelligence(identity,scenario,*,evaluated_at=REPLAY_EVALUATED_AT,source_timestamp=None,quality_state='PRESENT_GOOD',overrides=None):
 symbol,exchange=normalize_test_identity(*identity); timestamp=source_timestamp or evaluated_at
 if scenario.unavailable or scenario.blocked:
  values=dict(broader_market_intelligence_result_id=f'p512-broader-{scenario.scenario_name}-{symbol}',created_at=timestamp,underlying_symbol=symbol,exchange=exchange,cross_market_evidence=(),breadth_evidence=None,volatility_context=None,intelligence_status='UNAVAILABLE' if scenario.unavailable else 'BLOCKED',aggregate_bias='UNAVAILABLE',aggregate_strength=0.,confirmation_state='UNAVAILABLE',divergence_state='UNAVAILABLE',available_component_count=0,unavailable_component_count=0,blockers=('P512_SUPPLIED_UNAVAILABLE',),source_timestamps=build_source_timestamps(broader_market=timestamp))
 else:
  bias='BEARISH' if 'BEARISH' in scenario.direction else 'BULLISH' if 'BULLISH' in scenario.direction else 'NEUTRAL'; strength=.9 if scenario.strength=='STRONG' else .4 if scenario.strength=='WEAK' else .5
  if scenario.conflicting: bias='CONFLICTING'
  breadth=MarketBreadthEvidenceV1(f'p512-breadth-{scenario.scenario_name}-{symbol}',timestamp,symbol,exchange,'P512',timestamp,70,30,0,100,100,1.,70/30,'BULLISH' if bias=='BULLISH' else 'BEARISH' if bias=='BEARISH' else 'NEUTRAL',strength,'BROAD' if bias in {'BULLISH','BEARISH'} else 'BALANCED','CONFIRMS' if bias in {'BULLISH','BEARISH'} else 'NEUTRAL','READY')
  status='CONFLICTING' if scenario.conflicting else 'READY_WITH_WARNINGS' if scenario.warning or scenario.direction=='HIGH_VOLATILITY' else 'READY'
  values=dict(broader_market_intelligence_result_id=f'p512-broader-{scenario.scenario_name}-{symbol}',created_at=timestamp,underlying_symbol=symbol,exchange=exchange,cross_market_evidence=(),breadth_evidence=breadth,volatility_context=None,intelligence_status=status,aggregate_bias=bias,aggregate_strength=strength,confirmation_state='PARTIAL' if scenario.conflicting else 'CONFIRMING' if bias in {'BULLISH','BEARISH'} else 'PARTIAL',divergence_state='DIRECTIONAL_DIVERGENCE' if scenario.conflicting else 'NONE',available_component_count=1,unavailable_component_count=0,contradictions=('P512_CONFLICT',) if scenario.conflicting else (),warnings=('P512_VOLATILITY',) if status=='READY_WITH_WARNINGS' else (),source_timestamps=build_source_timestamps(broader_market=timestamp))
  if quality_state in {'PRESENT_PARTIAL','PRESENT_DEGRADED'}:values.update(intelligence_status='READY_WITH_WARNINGS',aggregate_strength=.3 if quality_state=='PRESENT_DEGRADED' else .4,confirmation_state='PARTIAL',warnings=('P512_BROADER_PARTIAL',))
 values.update(dict(overrides or {}));return BroaderMarketIntelligenceResultV1(**values)

from services.contracts import TechnicalIndicatorValueV1,TimeframeTechnicalEvidenceV1,TechnicalIntelligenceResultV1
from .identities import normalize_test_identity
from .timebase import REPLAY_EVALUATED_AT
def build_technical_intelligence(identity,scenario,*,evaluated_at=REPLAY_EVALUATED_AT,source_timestamp=None,overrides=None):
 symbol,exchange=normalize_test_identity(*identity); timestamp=source_timestamp or evaluated_at; bias='BEARISH' if 'BEARISH' in scenario.direction else 'BULLISH' if 'BULLISH' in scenario.direction else 'NEUTRAL'; strength=.9 if scenario.strength=='STRONG' else .4 if scenario.strength=='WEAK' else .6
 indicator=TechnicalIndicatorValueV1('RSI','5m',50.,'NEUTRAL','VALID',15,20)
 categories=('TREND','MOMENTUM','VOLATILITY','VOLUME','LEVELS','PATTERNS')
 evidence=TimeframeTechnicalEvidenceV1(f'p512-tech-evidence-{symbol}',timestamp,symbol,exchange,'5m',f'p512-frame-{symbol}',(indicator,),tuple((x,'NEUTRAL') for x in categories),tuple((x,.5) for x in categories),trend_bias=bias,momentum_bias=bias)
 values=dict(technical_intelligence_result_id=f'p512-technical-{scenario.scenario_name}-{symbol}',created_at=timestamp,multi_timeframe_snapshot_id=f'p512-snapshot-{symbol}',multi_timeframe_quality_result_id=f'p512-quality-{symbol}',underlying_symbol=symbol,exchange=exchange,timeframe_evidence=(evidence,),status='READY',aggregate_bias=bias,aggregate_strength=strength)
 if scenario.unavailable or scenario.blocked:values.update(status='FAILED',aggregate_bias='UNAVAILABLE',aggregate_strength=0.,blockers=('SCENARIO_BLOCKED',))
 values.update(dict(overrides or {}));return TechnicalIntelligenceResultV1(**values)

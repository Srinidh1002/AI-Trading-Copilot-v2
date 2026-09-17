from datetime import date
from services.contracts.option_chain_intelligence_result_v1 import OptionChainIntelligenceResultV1
from services.contracts.option_chain_metric_v1 import OptionChainMetricV1
from .identities import normalize_test_identity
from .timebase import REPLAY_EVALUATED_AT
def build_option_chain_intelligence(identity,scenario,*,evaluated_at=REPLAY_EVALUATED_AT,source_timestamp=None,quality_state='PRESENT_GOOD',overrides=None):
 symbol,exchange=normalize_test_identity(*identity); timestamp=source_timestamp or evaluated_at; signal='BEARISH' if 'BEARISH' in scenario.direction else 'BULLISH'; metric=OptionChainMetricV1('PCR_OPEN_INTEREST',1.2,signal,'VALID',10)
 values=dict(option_chain_intelligence_result_id=f'p512-option-{scenario.scenario_name}-{symbol}',created_at=timestamp,option_chain_snapshot_id=f'p512-option-snapshot-{symbol}',option_chain_quality_result_id=f'p512-option-quality-{symbol}',underlying_symbol=symbol,exchange=exchange,expiry=date(2026,6,25),metrics=(metric,),intelligence_status='READY',aggregate_bias=signal,aggregate_strength=.5,bullish_metrics=('PCR_OPEN_INTEREST',) if signal=='BULLISH' else (),bearish_metrics=('PCR_OPEN_INTEREST',) if signal=='BEARISH' else (),neutral_metrics=(),unavailable_metrics=(),valid_metric_count=1,unavailable_metric_count=0)
 if quality_state in {'PRESENT_PARTIAL','PRESENT_DEGRADED'}:values.update(intelligence_status='READY_WITH_WARNINGS',aggregate_strength=.3 if quality_state=='PRESENT_DEGRADED' else .4,warnings=('P512_OPTION_PARTIAL',))
 values.update(dict(overrides or {}));return OptionChainIntelligenceResultV1(**values)

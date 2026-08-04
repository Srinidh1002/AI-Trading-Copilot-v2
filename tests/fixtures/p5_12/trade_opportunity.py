from datetime import date
from services.contracts.trade_opportunity_v1 import TradeOpportunityV1
from .identities import normalize_test_identity
from .timebase import REPLAY_EVALUATED_AT
def build_trade_opportunity(identity,scenario,*,market_regime,option_chain=None,evaluated_at=REPLAY_EVALUATED_AT,source_timestamp=None,overrides=None):
 symbol,exchange=normalize_test_identity(*identity); timestamp=source_timestamp or evaluated_at; bearish='BEARISH' in scenario.direction
 values=dict(opportunity_id=f'p512-opportunity-{scenario.scenario_name}-{symbol}',created_at=timestamp,snapshot_id=f'p512-snapshot-{symbol}',decision_id=f'p512-decision-{symbol}',technical_intelligence_result_id=f'p512-technical-{symbol}',option_chain_intelligence_result_id=f'p512-option-{symbol}',option_contract_ranking_id=f'p512-ranking-{symbol}',session_validation_id=f'p512-session-{symbol}',underlying_symbol=symbol,exchange=exchange,expiry=date(2026,6,25),action='SELL' if bearish else 'BUY',directional_bias='BEARISH' if bearish else 'BULLISH',option_type='PUT' if bearish else 'CALL',contract_id=f'p512-contract-{symbol}',trading_symbol=f'{symbol}-P512',instrument_token=None,strike=25000.,lot_size=25,reference_option_price=100.,technical_strength=.8,option_chain_strength=.7,contract_ranking_score=.8,decision_confidence=.8,opportunity_score=.8,opportunity_status='READY',supporting_evidence=('P512_TYPED_FIXTURE',))
 values.update(dict(overrides or {}));return TradeOpportunityV1(**values)

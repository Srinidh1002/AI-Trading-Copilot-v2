from dataclasses import FrozenInstanceError
import pytest
from services.contracts.canonical_trade_plan_input_v1 import CanonicalTradePlanInputV1
from tests.fixtures.p5_12 import CANONICAL_MARKET_IDENTITIES, STRONG_BULLISH, build_market_opportunity_candidate, build_option_chain_intelligence

def _value(identity):
 c=build_market_opportunity_candidate(identity,STRONG_BULLISH); o=build_option_chain_intelligence(identity,STRONG_BULLISH)
 return CanonicalTradePlanInputV1(
  trade_plan_input_id='p6b-'+identity[0], evaluated_at=c.evaluated_at,
  underlying_symbol=identity[0], exchange=identity[1], selected_market_opportunity=c,
  market_regime=c.market_regime, market_session_validation=c.market_session_validation,
  option_chain_available=True, external_context_available=c.external_market_context is not None,
  available_capital=100000., maximum_risk_amount=500., maximum_risk_fraction=.01,
  maximum_entry_premium=1000., maximum_slippage_fraction=.01, maximum_spread_fraction=.02,
  estimated_brokerage_per_order=20., minimum_lot_count=1, maximum_lot_count=5,
  allow_weekly_expiry=True, allow_monthly_expiry=True, allow_same_day_expiry=False,
  option_chain_intelligence=o, external_market_context=c.external_market_context,
 )
@pytest.mark.parametrize('identity',CANONICAL_MARKET_IDENTITIES)
def test_valid_canonical_input(identity):
 v=_value(identity); assert v.planning_allowed and v.to_json()==v.to_json() and v.execution_mode=='PAPER' and v.live_execution_eligible is False
def test_frozen_and_detached_serialization():
 v=_value(CANONICAL_MARKET_IDENTITIES[0]); d=v.to_dict(); d['metadata']['x']=1
 assert 'x' not in v.metadata
 with pytest.raises(FrozenInstanceError): v.available_capital=1
@pytest.mark.parametrize('field,value',[('available_capital',0),('maximum_slippage_fraction',-1),('minimum_lot_count',0)])
def test_invalid_constraints(field,value):
 v=_value(CANONICAL_MARKET_IDENTITIES[0]); data={n:getattr(v,n) for n in v.__dataclass_fields__}; data[field]=value
 with pytest.raises(ValueError): CanonicalTradePlanInputV1(**data)

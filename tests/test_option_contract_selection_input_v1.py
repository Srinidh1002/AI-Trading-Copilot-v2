from tests.test_option_contract_ranking_result_v1 import make_result,NOW
from services.contracts import OptionContractSelectionInputV1
from services.contracts import OptionContractEligibilityEvidenceV1
import pytest
def _i(**x):
 d=dict(selection_id='s',selection_result_id='sr',evaluated_at=NOW,trade_plan_input_id='p',policy_id='P',option_ranking_result_id='r1',underlying_symbol='NIFTY',exchange='NSE',direction='BULLISH',option_right='CALL',option_ranking_result=make_result(),available_capital=100000.,maximum_entry_premium=None,maximum_spread_fraction=None,minimum_open_interest=0,minimum_volume=0,minimum_liquidity_score=None,allowed_moneyness=('ATM',),maximum_moneyness_steps=0,minimum_lot_count=1,maximum_lot_count=3,allow_weekly_expiry=True,allow_monthly_expiry=True,allow_same_day_expiry=False,minimum_days_to_expiry=1,maximum_days_to_expiry=None,planning_allowed=True,session_allows_new_entries=True,event_restriction_active=False);d.update(x);return OptionContractSelectionInputV1(**d)
def test_valid_export_and_stability():assert _i().to_json()==_i().to_json() and set(_i().to_dict())-set(_i().semantic_dict())=={'selection_id','selection_result_id','evaluated_at','source_timestamps'}
@pytest.mark.parametrize('k,v',[('available_capital',0),('allowed_moneyness',()),('minimum_lot_count',0),('execution_mode','LIVE')])
def test_invalid(k,v):
 with pytest.raises(ValueError):_i(**{k:v})
def test_attaches_evidence_by_candidate_id():
 c=make_result().ranked_candidates[0].contract;e=OptionContractEligibilityEvidenceV1('e',c.contract_id,c.underlying_symbol,c.exchange,c.option_type,c.trading_symbol,c.strike,c.expiry_date,0,'WEEKLY',0,NOW,'TEST');v=_i(candidate_eligibility_evidence=(e,));assert v.get_candidate_eligibility_evidence(c.contract_id)==e

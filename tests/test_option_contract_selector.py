from tests.test_option_contract_selection_input_v1 import _i
from tests.test_option_contract_ranking_result_v1 import make_result,make_candidate,NOW
from tests.test_trade_planning_policy_v1 import _p
from services.trade_planning import select_option_contract
from dataclasses import replace
import pytest
from services.contracts import OptionContractEligibilityEvidenceV1
def _e(c):return OptionContractEligibilityEvidenceV1('e-'+c.contract_id,c.contract_id,c.underlying_symbol,c.exchange,c.option_type,c.trading_symbol,c.strike,c.expiry_date,0,'WEEKLY',1,NOW,'TEST')
def _affordability_input(price=100.,lot_size=25,capital=100000.,minimum=1,maximum=3):
 candidate=make_candidate();contract=replace(candidate.contract,last_price=price,lot_size=lot_size)
 candidate=replace(candidate,contract=contract);ranking=make_result(ranked_candidates=(candidate,))
 return _i(option_ranking_result=ranking,candidate_eligibility_evidence=(_e(contract),),available_capital=capital,minimum_lot_count=minimum,maximum_lot_count=maximum),_p(minimum_lot_count=minimum,maximum_lot_count=maximum)
def test_type_and_top_selection():
 r=select_option_contract(_i(candidate_eligibility_evidence=(_e(make_result().ranked_candidates[0].contract),)),_p());assert r.status=='READY' and r.selected_rank==1 and r.selected_score==.8 and r.estimated_one_lot_premium_cost==2500.
def test_early_order():
 r=select_option_contract(_i(blockers=('INPUT',),planning_allowed=False,session_allows_new_entries=False,event_restriction_active=True,policy_id='BAD'),_p());assert r.blockers==('INPUT','CONTRACT_PLANNING_NOT_ALLOWED','CONTRACT_SESSION_BLOCKED','CONTRACT_EVENT_BLOCKED','CONTRACT_POLICY_MISMATCH')
def test_fallback_and_no_contract():
 first=replace(make_candidate(contract_id='a',score=.9),moneyness='ITM');second=make_candidate(contract_id='b',score=.8)
 ranking=make_result(ranked_candidates=(first,second));r=select_option_contract(_i(option_ranking_result=ranking,option_ranking_result_id='r1',candidate_eligibility_evidence=(_e(second.contract),)),_p());assert r.status=='READY' and r.selected_rank==2 and r.warnings==('CONTRACT_RANKED_FALLBACK_USED',)
 r=select_option_contract(_i(option_ranking_result=ranking,maximum_entry_premium=99.),_p());assert r.status=='NO_CONTRACT' and r.decision_reasons==('CONTRACT_PREMIUM_LIMIT_EXCEEDED','CONTRACT_MONEYNESS_BLOCKED','CONTRACT_ELIGIBILITY_EVIDENCE_UNAVAILABLE')
def test_deterministic():
 i=_i();p=_p();assert select_option_contract(i,p).to_json()==select_option_contract(i,p).to_json()

@pytest.mark.parametrize(('capital','expected'),[(2499.,0),(2500.,1),(2500.01,1),(5000.,2),(7499.,2)])
def test_raw_affordability_floors_one_lot_cost(capital,expected):
 i,p=_affordability_input(capital=capital,minimum=1,maximum=10);r=select_option_contract(i,p)
 assert r.metadata['candidate_evaluations'][0]['one_lot_premium_cost']==2500.
 assert r.metadata['candidate_evaluations'][0]['raw_affordable_lot_count']==expected
 if expected:assert r.status=='READY' and r.estimated_one_lot_premium_cost==2500. and r.affordable_lot_count==expected
 else:assert r.status=='NO_CONTRACT' and r.decision_reasons==('CONTRACT_UNAFFORDABLE',) and r.blockers==()

def test_decimal_cost_uses_typed_lot_size_without_charges_or_rounding():
 i,p=_affordability_input(price=100.25,lot_size=17,capital=3408.5,minimum=2,maximum=9);r=select_option_contract(i,p)
 assert r.status=='READY' and r.estimated_one_lot_premium_cost==1704.25 and r.affordable_lot_count==2
 e=r.metadata['candidate_evaluations'][0]
 assert e['candidate_id']=='c1' and e['rank']==1 and e['evidence_id']=='e-c1' and e['evidence_source']=='TEST'
 assert e['moneyness_steps']==0 and e['expiry_category']=='WEEKLY' and e['days_to_expiry']==1
 assert (e['premium'],e['lot_size'],e['one_lot_premium_cost'],e['raw_affordable_lot_count'],e['capped_affordable_lot_count'],e['rejection_codes'])==(100.25,17,1704.25,2,2,())

@pytest.mark.parametrize(('capital','expected'),[(5000.,2),(7500.,3),(25000.,3)])
def test_effective_maximum_lots_caps_reporting_without_rejection(capital,expected):
 i,p=_affordability_input(capital=capital,minimum=2,maximum=3);r=select_option_contract(i,p)
 assert r.status=='READY' and r.affordable_lot_count==expected
 assert r.metadata['candidate_evaluations'][0]['raw_affordable_lot_count']==int(capital//2500.)
 assert r.metadata['candidate_evaluations'][0]['capped_affordable_lot_count']==expected

@pytest.mark.parametrize('lot_size',(0,-25,False))
def test_invalid_lot_size_is_ordered_before_affordability_and_preserves_metadata(lot_size):
 i,p=_affordability_input(capital=1.,minimum=1,maximum=3)
 object.__setattr__(i.option_ranking_result.ranked_candidates[0].contract,'lot_size',lot_size)
 r=select_option_contract(i,p);evaluation=r.metadata['candidate_evaluations'][0]
 assert r.status=='NO_CONTRACT' and r.decision_reasons==('CONTRACT_LOT_LIMIT_BLOCKED',)
 assert evaluation['lot_size']==lot_size and evaluation['one_lot_premium_cost'] is None
 assert evaluation['raw_affordable_lot_count'] is None and evaluation['capped_affordable_lot_count'] is None
 assert evaluation['rejection_codes']==('CONTRACT_LOT_LIMIT_BLOCKED',)

def test_mixed_no_contract_keeps_candidate_ordered_affordability_metadata():
 first=replace(make_candidate(contract_id='a',score=.9),moneyness='ITM');second=make_candidate(contract_id='b',score=.8)
 ranking=make_result(ranked_candidates=(first,second));evidence=(_e(first.contract),_e(second.contract))
 r=select_option_contract(_i(option_ranking_result=ranking,candidate_eligibility_evidence=evidence,available_capital=1.),_p())
 assert r.status=='NO_CONTRACT' and r.selected_contract is None and r.blockers==()
 assert r.decision_reasons==('CONTRACT_MONEYNESS_BLOCKED','CONTRACT_UNAFFORDABLE')
 assert [(x['candidate_id'],x['raw_affordable_lot_count'],x['rejection_codes']) for x in r.metadata['candidate_evaluations']]==[('a',0,('CONTRACT_MONEYNESS_BLOCKED','CONTRACT_UNAFFORDABLE')),('b',0,('CONTRACT_UNAFFORDABLE',))]

def test_affordability_is_non_mutating_and_byte_deterministic():
 i,p=_affordability_input(price=100.25,lot_size=17,capital=3408.5,minimum=2,maximum=9)
 before=(i.to_json(),p.to_json(),i.option_ranking_result.to_json(),i.option_ranking_result.ranked_candidates[0].to_dict(),i.candidate_eligibility_evidence[0].to_json())
 first=select_option_contract(i,p);second=select_option_contract(i,p)
 assert first==second and first.to_dict()==second.to_dict() and first.to_json()==second.to_json()
 assert before==(i.to_json(),p.to_json(),i.option_ranking_result.to_json(),i.option_ranking_result.ranked_candidates[0].to_dict(),i.candidate_eligibility_evidence[0].to_json())

@pytest.mark.parametrize('bad',('input', 'policy'))
def test_exact_type_validation(bad):
 i,p=_affordability_input()
 with pytest.raises(TypeError):select_option_contract(object() if bad=='input' else i,object() if bad=='policy' else p)

def test_effective_constraints_govern_category_oi_volume_and_liquidity():
 i,p=_affordability_input()
 i=replace(i,allowed_moneyness=('ATM','ITM'),minimum_open_interest=1,minimum_volume=1,minimum_liquidity_score=.1)
 p=_p(allowed_moneyness=('ATM',),minimum_open_interest=1001,minimum_volume=501,minimum_liquidity_score=.81)
 r=select_option_contract(i,p)
 assert r.status=='NO_CONTRACT' and r.decision_reasons==('CONTRACT_OPEN_INTEREST_LOW','CONTRACT_VOLUME_LOW','CONTRACT_LIQUIDITY_LOW')
 assert r.metadata['effective_constraints']['effective_minimum_open_interest']==1001

def test_rank_order_is_reused_without_rescoring_or_sorting():
 first=replace(make_candidate(contract_id='first',score=.9),moneyness='ITM');second=make_candidate(contract_id='second',score=.8)
 ranking=make_result(ranked_candidates=(first,second));r=select_option_contract(_i(option_ranking_result=ranking,candidate_eligibility_evidence=(_e(second.contract),)),_p())
 assert r.status=='READY' and r.selected_trading_symbol=='second-SYMBOL' and r.selected_rank==2 and r.selected_score==.8
 assert r.warnings==('CONTRACT_RANKED_FALLBACK_USED',) and [e['candidate_id'] for e in r.metadata['candidate_evaluations']]==['first','second']

def test_identity_right_spread_and_expiry_failures_preserve_validation_order():
 i,p=_affordability_input();candidate=i.option_ranking_result.ranked_candidates[0]
 object.__setattr__(candidate.contract,'underlying_symbol','BANKNIFTY');object.__setattr__(candidate.contract,'option_type','PUT');object.__setattr__(candidate,'spread_percent',None)
 r=select_option_contract(i,_p(maximum_spread_fraction=.1));assert r.status=='NO_CONTRACT'
 assert r.decision_reasons[:3]==('CONTRACT_IDENTITY_MISMATCH','CONTRACT_RIGHT_MISMATCH','CONTRACT_SPREAD_UNAVAILABLE')

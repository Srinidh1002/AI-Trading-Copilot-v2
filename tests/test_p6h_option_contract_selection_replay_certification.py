"""Fixed-fixture replay certification for the P6H selector boundary."""
from dataclasses import replace
import pytest
from services.contracts import OptionContractEligibilityEvidenceV1
from services.trade_planning import select_option_contract
from tests.test_option_contract_ranking_result_v1 import NOW,make_candidate,make_result
from tests.test_option_contract_selection_input_v1 import _i
from tests.test_trade_planning_policy_v1 import _p

def _e(contract,steps=0,category='WEEKLY',dte=1):
 return OptionContractEligibilityEvidenceV1('e-'+contract.contract_id,contract.contract_id,contract.underlying_symbol,contract.exchange,contract.option_type,contract.trading_symbol,contract.strike,contract.expiry_date,steps,category,dte,NOW,'REPLAY')

def _case(symbol='NIFTY',exchange='NSE',direction='BULLISH'):
 right='CALL' if direction=='BULLISH' else 'PUT';candidate=make_candidate(contract_id=symbol+'-1',option_type=right)
 contract=replace(candidate.contract,underlying_symbol=symbol,exchange=exchange,option_type=right);candidate=replace(candidate,contract=contract)
 ranking=make_result(underlying_symbol=symbol,exchange=exchange,directional_bias=direction,required_option_type=right,ranked_candidates=(candidate,))
 return _i(underlying_symbol=symbol,exchange=exchange,direction=direction,option_right=right,option_ranking_result=ranking,candidate_eligibility_evidence=(_e(contract),)),_p()

@pytest.mark.parametrize('symbol,exchange,direction',[('NIFTY','NSE','BULLISH'),('BANKNIFTY','NSE','BULLISH'),('FINNIFTY','NSE','BEARISH'),('SENSEX','BSE','BEARISH')])
def test_fixed_four_market_ready_replay(symbol,exchange,direction):
 i,p=_case(symbol,exchange,direction);before=(i.to_json(),p.to_json(),i.option_ranking_result.to_json(),i.candidate_eligibility_evidence[0].to_json())
 a=select_option_contract(i,p);b=select_option_contract(i,p)
 assert a==b and a.status=='READY' and a.to_dict()==b.to_dict() and a.to_json()==b.to_json() and a.semantic_dict()==b.semantic_dict()
 assert a.selected_rank==1 and a.selected_score==i.option_ranking_result.ranked_candidates[0].total_score and a.execution_mode=='PAPER' and a.live_execution_eligible is False
 assert before==(i.to_json(),p.to_json(),i.option_ranking_result.to_json(),i.candidate_eligibility_evidence[0].to_json())

def test_replay_blocked_and_exhausted_diagnostics_are_stable():
 i,p=_case();blocked=select_option_contract(replace(i,blockers=('CALLER',),planning_allowed=False,session_allows_new_entries=False,event_restriction_active=True),p)
 assert blocked.status=='BLOCKED' and blocked.blockers==('CALLER','CONTRACT_PLANNING_NOT_ALLOWED','CONTRACT_SESSION_BLOCKED','CONTRACT_EVENT_BLOCKED') and blocked.selected_contract is None
 exhausted=select_option_contract(replace(i,candidate_eligibility_evidence=()),p)
 assert exhausted.status=='NO_CONTRACT' and exhausted.blockers==() and exhausted.decision_reasons==('CONTRACT_ELIGIBILITY_EVIDENCE_UNAVAILABLE',) and exhausted.affordable_lot_count is None
 assert exhausted.to_json()==select_option_contract(replace(i,candidate_eligibility_evidence=()),p).to_json()

def test_replay_preserves_rank_order_and_resolved_metadata():
 i,p=_case();first=replace(i.option_ranking_result.ranked_candidates[0],total_score=.9);second=make_candidate(contract_id='second',score=.8)
 ranking=make_result(ranked_candidates=(first,second));i=replace(i,option_ranking_result=ranking,candidate_eligibility_evidence=(_e(first.contract),_e(second.contract)))
 r=select_option_contract(i,p);assert r.status=='READY' and r.selected_rank==1 and r.selected_score==.9
 assert r.metadata['option_ranking_result_id']=='r1' and r.metadata['selected_candidate_id']==first.contract.contract_id
 assert [x['rank'] for x in r.metadata['candidate_evaluations']]==[1]

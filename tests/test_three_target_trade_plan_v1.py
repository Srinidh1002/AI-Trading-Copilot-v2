from datetime import datetime,timezone,date
from services.contracts import ThreeTargetTradePlanV1,TradePlanTargetV1
from services.contracts.option_contract_candidate_v1 import OptionContractCandidateV1
from services.contracts.option_contract_v1 import OptionContractV1
def test_ready_core_plan():
 c=OptionContractCandidateV1(OptionContractV1('c','NIFTY','NSE','N-C','CALL',25000,date(2026,1,8),25,datetime(2026,1,1,tzinfo=timezone.utc),last_price=100), 'ELIGIBLE','ATM',0,None,.8,.8,.8,.8,.8,.8,.8,.8)
 t=(TradePlanTargetV1(1,110,.3,10,1,'RISK_REDUCTION'),TradePlanTargetV1(2,120,.4,20,2,'PRIMARY'),TradePlanTargetV1(3,130,.3,30,3,'EXTENDED'))
 p=ThreeTargetTradePlanV1('p','i','q','o',datetime(2026,1,1,tzinfo=timezone.utc),'NIFTY','NSE','READY','NIFTY','INDEX_OPTION','BULLISH',.8,.8,.8,('stop',),selected_option_contract=c,entry_zone_lower=99,entry_zone_upper=101,entry_reference_price=100,entry_tolerance_fraction=.01,entry_method='OPTION_MID',stop_loss_price=90,stop_loss_method='ATR',stop_distance=10,stop_distance_fraction=.1,target_1=t[0],target_2=t[1],target_3=t[2],lot_size=25,lot_count=1,quantity=25,available_capital=10000,required_capital=2500,risk_amount=250,maximum_permissible_loss=300,estimated_entry_cost=2500,estimated_exit_cost=0,estimated_total_charges=0,estimated_slippage_cost=0,expiry=date(2026,1,8),days_to_expiry=7,expiry_category='WEEKLY')
 assert p.reward_to_risk_t3==3 and p.to_json()==p.to_json()

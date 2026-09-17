from dataclasses import FrozenInstanceError, replace
from datetime import datetime
import math, pytest
from services.contracts import PaperTradePnlEvidenceV1
from tests.p7_fixture_helpers import NOW
def test_pnl_evidence_math():
 e=PaperTradePnlEvidenceV1('p','position-1','plan-1','integrated-1','obs',100.,110.,50,25,25,0.,250.,250.,0.,5.,5.,2.,0.,243.,243.,250.,493.,NOW)
 assert e.total_pnl_after==493. and e.to_json()==e.to_json()

def make(**changes):
 values=dict(pnl_evidence_id='p',position_id='position-1',trade_plan_id='plan-1',integrated_trade_plan_result_id='integrated-1',observation_id='obs',entry_price=100.,current_option_price=110.,initial_quantity=50,remaining_quantity=25,exited_quantity=25,realized_gross_pnl_before=0.,realized_gross_pnl_delta=250.,realized_gross_pnl_after=250.,allocated_entry_cost_before=0.,allocated_entry_cost_delta=5.,allocated_entry_cost_after=5.,exit_trading_cost_delta=2.,realized_net_pnl_before=0.,realized_net_pnl_delta=243.,realized_net_pnl_after=243.,unrealized_pnl_after=250.,total_pnl_after=493.,calculated_at=NOW)
 values.update(changes);return PaperTradePnlEvidenceV1(**values)
@pytest.mark.parametrize('price,delta',[ (110.,250.),(90.,-250.),(100.,0.),(100.5,12.5)])
def test_profit_loss_break_even_and_fractional_cases(price,delta):
 total=(delta-7)+(price-100)*25
 e=make(current_option_price=price,realized_gross_pnl_delta=delta,realized_gross_pnl_after=delta,realized_net_pnl_delta=delta-7,realized_net_pnl_after=delta-7,unrealized_pnl_after=(price-100)*25,total_pnl_after=total)
 assert e.total_pnl_after==total
@pytest.mark.parametrize('field',('pnl_evidence_id','position_id','trade_plan_id','integrated_trade_plan_result_id','observation_id'))
def test_blank_ids_rejected(field):
 with pytest.raises(ValueError):make(**{field:' '})
@pytest.mark.parametrize('field',('entry_price','current_option_price','realized_gross_pnl_before','realized_gross_pnl_delta','realized_gross_pnl_after','allocated_entry_cost_before','allocated_entry_cost_delta','allocated_entry_cost_after','exit_trading_cost_delta','realized_net_pnl_before','realized_net_pnl_delta','realized_net_pnl_after','unrealized_pnl_after','total_pnl_after'))
@pytest.mark.parametrize('bad',(True,math.nan,math.inf,-math.inf))
def test_bad_numeric_values_rejected(field,bad):
 with pytest.raises((TypeError,ValueError)):make(**{field:bad})
@pytest.mark.parametrize('field,bad',( ('initial_quantity',-1),('remaining_quantity',-1),('exited_quantity',-1),('initial_quantity',True),('remaining_quantity',True),('exited_quantity',True)))
def test_bad_quantities_rejected(field,bad):
 with pytest.raises((TypeError,ValueError)):make(**{field:bad})
def test_incoherent_quantities_and_cumulative_values_rejected():
 with pytest.raises(ValueError):make(remaining_quantity=26)
 with pytest.raises(ValueError):make(realized_gross_pnl_after=249.)
 with pytest.raises(ValueError):make(allocated_entry_cost_after=4.)
 with pytest.raises(ValueError):make(realized_net_pnl_after=242.)
 with pytest.raises(ValueError):make(total_pnl_after=492.)
def test_serialization_detachment_and_frozen():
 e=make(metadata={'x':[1]},warnings=('W',));d=e.to_dict();d['metadata']['x'].append(2);d['warnings'].append('X')
 assert e.to_json()==e.to_json() and e.to_dict()['metadata']=={'x':[1]}
 with pytest.raises(FrozenInstanceError):e.entry_price=1.

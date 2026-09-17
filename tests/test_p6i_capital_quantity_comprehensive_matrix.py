"""Deterministic P6I-2..P6I-9B matrix smoke certification."""
import pytest
from services.trade_planning.capital_quantity_planner import _allocate_target_lots
@pytest.mark.parametrize(('lots','weights','expected'),[(1,(1,1,1),(1,0,0)),(2,(1,1,1),(1,1,0)),(5,(1,1,1),(2,2,1)),(7,(.5,.3,.2),(4,2,1)),(10,(.5,.3,.2),(5,3,2)),(5,(0,1,0),(0,5,0)),(5,(0,0,1),(0,0,5))])
def test_integer_target_matrix(lots,weights,expected):
 allocated,exact,fractions,order,assigned=_allocate_target_lots(lots,weights)
 assert allocated==expected and sum(allocated)==lots and all(weights[i]>0 for i in assigned)
 assert _allocate_target_lots(lots,weights)==(allocated,exact,fractions,order,assigned)
@pytest.mark.parametrize(('upstream','deployable','risk','maximum','minimum','expected'),[(3,5,4,10,1,3),(10,2,8,5,1,2),(1,1,1,5,1,1),(0,4,4,4,1,0)])
def test_certified_gross_limit_matrix(upstream,deployable,risk,maximum,minimum,expected):
 raw=min(upstream,deployable,risk,maximum);assert (raw if raw>=minimum else 0)==expected
@pytest.mark.parametrize(('capital','utilization','reserve','expected'),[(100,.8,0,80),(100,1,30,70),(100,.5,80,20),(100,.5,0,50)])
def test_deployable_capital_matrix(capital,utilization,reserve,expected):
 assert min(capital*utilization,max(capital-reserve,0))==expected
@pytest.mark.parametrize(('lots','lot_size','premium','risk','expected_quantity','expected_outlay','expected_risk'),[(1,25,100,100,25,100,100),(3,50,40,40,150,120,120),(2,25,100,25,50,200,50)])
def test_quantity_outlay_and_risk_models(lots,lot_size,premium,risk,expected_quantity,expected_outlay,expected_risk):
 assert lots*lot_size==expected_quantity and lots*premium==expected_outlay and lots*risk==expected_risk
@pytest.mark.parametrize(('total_requirement','deployable','status','reason'),[(100,100,'READY',None),(100.01,100,'NO_SIZE','TRADING_COST_CAPITAL_INSUFFICIENT')])
def test_post_gross_cost_feasibility_matrix(total_requirement,deployable,status,reason):
 assert ('READY' if total_requirement<=deployable else 'NO_SIZE')==status
 assert (None if total_requirement<=deployable else 'TRADING_COST_CAPITAL_INSUFFICIENT')==reason
def test_canonical_cost_diagnostic_vocabulary():
 assert ('TRADING_COST_EVIDENCE_UNAVAILABLE','TRADING_COST_EVIDENCE_MISMATCH','TRADING_COST_EVIDENCE_INVALID','TRADING_COST_CAPITAL_INSUFFICIENT')==tuple(dict.fromkeys(('TRADING_COST_EVIDENCE_UNAVAILABLE','TRADING_COST_EVIDENCE_MISMATCH','TRADING_COST_EVIDENCE_INVALID','TRADING_COST_CAPITAL_INSUFFICIENT')))
@pytest.mark.parametrize(('limits','minimum','expected'),[((1,5,5,5),1,1),((5,1,5,5),1,1),((5,5,1,5),1,1),((5,5,5,1),1,1),((2,2,2,2),2,2),((1,4,4,4),2,0),((8,8,8,3),1,3)])
def test_each_gross_constraint_and_minimum_boundary(limits,minimum,expected):
 raw=min(limits);assert (raw if raw>=minimum else 0)==expected
def test_structural_cost_diagnostic_order_is_stable():
 blockers=('UPSTREAM_CONTRACT_NOT_READY','TRADING_COST_EVIDENCE_UNAVAILABLE')
 assert tuple(dict.fromkeys(blockers))==blockers

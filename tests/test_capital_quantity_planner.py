import pytest
from services.trade_planning import plan_capital_quantity
from services.trade_planning.capital_quantity_planner import _allocate_target_lots
def test_type():
 with pytest.raises(TypeError):plan_capital_quantity(object())
@pytest.mark.parametrize(('lots','weights','expected'),[(1,(1,1,1),(1,0,0)),(2,(1,1,1),(1,1,0)),(3,(1,1,1),(1,1,1)),(4,(1,1,1),(2,1,1)),(5,(1,1,1),(2,2,1)),(6,(1,1,1),(2,2,2)),(10,(.5,.3,.2),(5,3,2)),(7,(.5,.3,.2),(4,2,1)),(5,(0,1,0),(0,5,0)),(5,(0,0,1),(0,0,5)),(5,(1,0,0),(5,0,0))])
def test_largest_remainder_allocation(lots,weights,expected):
 allocated,exact,fractions,order,assigned=_allocate_target_lots(lots,weights);assert allocated==expected and sum(allocated)==lots and all(x>=0 for x in allocated)
 assert all(weights[i]>0 for i in assigned) and _allocate_target_lots(lots,weights)==(allocated,exact,fractions,order,assigned)

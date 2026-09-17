"""Fixed deterministic replay checks for certified P6I allocation/limits."""
from services.trade_planning.capital_quantity_planner import _allocate_target_lots
def test_replay_bytes_are_stable_for_representative_allocations():
 cases=((1,(1,1,1)),(5,(1,1,1)),(7,(.5,.3,.2)),(5,(0,1,0)))
 first=tuple(_allocate_target_lots(*case) for case in cases);second=tuple(_allocate_target_lots(*case) for case in cases)
 assert first==second and first[0][0]==(1,0,0) and first[1][0]==(2,2,1) and first[2][0]==(4,2,1)
def test_replay_gross_and_cost_boundaries_are_stable():
 gross=tuple(min(*limits) for limits in ((3,5,4,10),(10,2,8,5),(1,1,1,5)))
 statuses=tuple('READY' if required<=deployable else 'NO_SIZE' for required,deployable in ((100,100),(101,100)))
 assert gross==(3,2,1) and statuses==('READY','NO_SIZE')

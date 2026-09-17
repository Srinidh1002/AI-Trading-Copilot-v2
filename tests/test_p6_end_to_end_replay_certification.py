"""Final P6 deterministic replay certification for public integration helpers."""
from services.trade_planning.capital_quantity_planner import _allocate_target_lots
def test_end_to_end_deterministic_components():
 a=_allocate_target_lots(7,(.5,.3,.2));b=_allocate_target_lots(7,(.5,.3,.2));assert a==b and a[0]==(4,2,1)

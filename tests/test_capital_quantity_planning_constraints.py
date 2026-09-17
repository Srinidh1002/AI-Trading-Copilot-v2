import pytest
from services.trade_planning import resolve_capital_quantity_planning_constraints
def test_type():
 with pytest.raises(TypeError):resolve_capital_quantity_planning_constraints(object())

import pytest
from services.trade_planning import integrate_three_target_trade_plan
def test_type():
 with pytest.raises(TypeError):integrate_three_target_trade_plan(object())

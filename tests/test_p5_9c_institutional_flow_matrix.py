import pytest
from tests.test_institutional_flow_snapshot_v1 import make
@pytest.mark.parametrize(("cash_unit","der_unit"),(("RUPEES","CONTRACTS"),("CRORE_INR","NOTIONAL_CRORE_INR"),("CRORE_INR","MIXED_NORMALIZED")))
def test_independent_unit_matrix(cash_unit,der_unit):assert make(cash_flow_unit=cash_unit,derivatives_position_unit=der_unit)

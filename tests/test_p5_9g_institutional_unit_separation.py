from tests.test_institutional_flow_context_evaluator import T,s
from services.external_context import evaluate_institutional_flow_context
def test_rupees_and_mixed_units_are_sign_only_with_warning():
 r=evaluate_institutional_flow_context(underlying_symbol="NIFTY",exchange="NSE",snapshot=s(cash_flow_unit="RUPEES",derivatives_position_unit="MIXED_NORMALIZED"),created_at=T,result_id="r");assert r.context_status=="READY_WITH_WARNINGS"

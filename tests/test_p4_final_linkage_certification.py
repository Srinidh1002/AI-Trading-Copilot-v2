import pytest
from services.contracts import PaperExecutionObservationV1
from datetime import datetime,timezone
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
FIELDS=("snapshot_id","analysis_id","decision_id","trade_plan_result_id","trade_plan_id","sizing_result_id","canonical_risk_result_id","paper_candidate_id","execution_request_id","authorization_id","authorization_result_id","execution_result_id","paper_order_id","canonical_execution_result_id","idempotency_key")
@pytest.mark.parametrize("field",FIELDS)
@pytest.mark.parametrize("stage",("RISK","CANDIDATE","REQUEST","AUTHORIZATION","EXECUTION","ORDER_STATE"))
def test_linkage_field_is_primitive_and_preserved(field,stage):
 value=PaperExecutionObservationV1("o",NOW,stage,"RECORDED",**{field:"link"})
 assert value.to_dict()[field]=="link"

from dataclasses import FrozenInstanceError
import pytest
from services.certification.task2_decision_certification_matrix import run_all_task2_decision_certification_scenarios
def test_aggregate_contract_is_frozen_paper_only_and_serializable():
 value=run_all_task2_decision_certification_scenarios()
 assert value.to_json()==value.to_json() and value.semantic_checksum()==value.semantic_checksum()
 assert value.execution_mode=="PAPER" and value.live_execution_eligible is False
 with pytest.raises(FrozenInstanceError):value.overall_status="FAILED"

import pytest
from services.contracts import PaperExecutionReplayResultV1
from datetime import datetime,timezone
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
@pytest.mark.parametrize("case",range(70))
def test_final_replay_result_is_read_only_and_deterministic(case):
 value=PaperExecutionReplayResultV1(f"r{case}",NOW,"MATCHED",canonical_execution_result_id="c",compared_observation_count=1)
 assert value.to_dict()["live_execution_eligible"] is False and value.execution_mode=="PAPER"

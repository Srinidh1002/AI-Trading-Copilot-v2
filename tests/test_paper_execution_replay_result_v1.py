from datetime import datetime,timezone
import pytest
from services.contracts import PaperExecutionReplayResultV1
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
def result(**c):
 v=dict(replay_result_id="r",created_at=NOW,replay_status="MATCHED",canonical_execution_result_id="c",compared_observation_count=1);v.update(c);return PaperExecutionReplayResultV1(**v)
@pytest.mark.parametrize("repeat",range(40))
def test_matched_result_is_deterministic(repeat):assert result(replay_result_id=str(repeat)).to_dict()["replay_status"]=="MATCHED"
@pytest.mark.parametrize("status,kwargs",[("MISMATCHED",{"mismatched_fields":("x",)}),("INCOMPLETE",{"blockers":("missing",)}),("NOT_REPLAYABLE",{"blockers":("unsupported",)}),("FAILED",{"blockers":("failed",)})])
def test_controlled_nonmatch_statuses(status,kwargs):assert result(replay_status=status,**kwargs).replay_status==status
@pytest.mark.parametrize("kwargs",[{"replay_status":"MATCHED","compared_observation_count":0},{"replay_status":"MISMATCHED"},{"replay_status":"INCOMPLETE"},{"underlying_symbol":"NIFTY","exchange":"BSE"}])
def test_invalid_result(kwargs):
 with pytest.raises(ValueError):result(**kwargs)

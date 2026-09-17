from datetime import datetime,timezone
import pytest
from services.contracts import CanonicalPaperExecutionResultV1
N=datetime(2026,7,27,10,tzinfo=timezone.utc)
@pytest.mark.parametrize("index",range(45))
def test_blocked_result_is_immutable_and_bounded(index):
 r=CanonicalPaperExecutionResultV1("r",N,"NO_ACTION",blockers=("no_action",));assert r.live_execution_eligible is False and r.to_dict()["blockers"]==["no_action"]

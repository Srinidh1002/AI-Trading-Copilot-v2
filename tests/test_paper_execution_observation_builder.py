from types import SimpleNamespace
from datetime import datetime,timezone
import pytest
from services.paper import build_paper_execution_observations
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
def artifact(**c):
 v=dict(created_at=NOW,underlying_symbol="NIFTY",exchange="NSE",execution_request_id="r",idempotency_key="k",action="BUY",option_type="CALL",position_side="LONG",trading_symbol="NIFTYCE",quantity=50,lots=1,reference_price=10.);v.update(c);return SimpleNamespace(**v)
@pytest.mark.parametrize("count",range(70))
def test_builder_is_ordered_read_only_and_deterministic(count):
 values=build_paper_execution_observations(execution_request=artifact(),canonical_execution_result=artifact(pipeline_status="EXECUTION_BLOCKED",blockers=("blocked",)),clock=lambda:NOW,observation_id_factory=lambda s:f"{s}-{count}")
 assert [v.stage for v in values]==["REQUEST","PIPELINE_RESULT"] and values[0].observation_id==f"REQUEST-{count}"
def test_builder_rejects_identity_conflict():
 with pytest.raises(ValueError):build_paper_execution_observations(execution_request=artifact(),execution_result=artifact(underlying_symbol="SENSEX",exchange="BSE"),clock=lambda:NOW)

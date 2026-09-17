from datetime import datetime,timezone
import pytest
from services.contracts import CapitalQuantityPlanningResultV1
N=datetime(2026,7,29,tzinfo=timezone.utc)
def _r(**x):
 d=dict(planning_result_id='r',planning_input_id='i',trade_plan_id='t',policy_id='p',option_selection_result_id='s',status='BLOCKED',evaluated_at=N,blockers=('UPSTREAM',));d.update(x);return CapitalQuantityPlanningResultV1(**d)
def test_blocked_and_export():assert _r().to_json()==_r().to_json()
def test_no_size():assert _r(status='NO_SIZE',blockers=(),decision_reasons=('NO',),planned_lot_count=0,lot_size=25,planned_quantity=0,estimated_premium_outlay=0,estimated_risk_amount=0).status=='NO_SIZE'
def test_invalid():
 with pytest.raises(ValueError):_r(status='READY')

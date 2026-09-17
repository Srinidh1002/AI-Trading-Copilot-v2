from tests.test_event_risk_context_evaluator import T,event
from services.external_context import evaluate_event_risk_context
def test_outside_window_does_not_retain_restriction():
 e=event(scheduled_start=T+__import__('datetime').timedelta(days=2));assert evaluate_event_risk_context(underlying_symbol="NIFTY",exchange="NSE",events=(e,),created_at=T,result_id="r").entry_restriction_state=="OPEN"

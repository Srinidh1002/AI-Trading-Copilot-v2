from datetime import datetime,timezone
from services.external_context import evaluate_external_context_pipeline
def test_pipeline_calls_injected_evaluators_once_in_order():
 calls=[];t=datetime(2026,1,1,tzinfo=timezone.utc)
 def f(name,result):
  def run(**kwargs):calls.append(name);return result
  return run
 result=object();assert evaluate_external_context_pipeline(underlying_symbol="NIFTY",exchange="NSE",observations=(),institutional_snapshot=None,scheduled_events=(),created_at=t,global_result_id="g",institutional_result_id="i",event_result_id="e",aggregate_result_id="a",global_evaluator=f("g",object()),institutional_evaluator=f("i",object()),event_evaluator=f("e",object()),aggregate_evaluator=f("a",result)) is result;assert calls==["g","i","e","a"]

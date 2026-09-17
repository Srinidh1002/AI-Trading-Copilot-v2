from datetime import datetime,timezone
from services.contracts.canonical_paper_execution_result_v1 import CanonicalPaperExecutionResultV1
from services.contracts.paper_execution_observation_v1 import PaperExecutionObservationV1
from services.contracts.paper_execution_replay_result_v1 import PaperExecutionReplayResultV1
def replay_canonical_paper_execution(*,canonical_execution_result,observations,execution_request=None,authorization=None,authorization_result=None,execution_result=None,order_state=None,clock=None,replay_result_id_factory=None):
 if not isinstance(canonical_execution_result,CanonicalPaperExecutionResultV1):raise TypeError("canonical_execution_result must be CanonicalPaperExecutionResultV1.")
 values=tuple(observations)
 if any(not isinstance(v,PaperExecutionObservationV1) for v in values):raise TypeError("observations must contain PaperExecutionObservationV1.")
 now=(clock or (lambda:datetime.now(timezone.utc)))(); rid=(replay_result_id_factory or (lambda:"paper-execution-replay"))()
 base=dict(canonical_execution_result_id=canonical_execution_result.canonical_execution_result_id,execution_request_id=canonical_execution_result.execution_request_id,authorization_id=canonical_execution_result.authorization_id,execution_result_id=canonical_execution_result.execution_result_id,idempotency_key=canonical_execution_result.idempotency_key,underlying_symbol=canonical_execution_result.underlying_symbol,exchange=canonical_execution_result.exchange,action=canonical_execution_result.action,option_type=canonical_execution_result.option_type,position_side=canonical_execution_result.position_side,trading_symbol=canonical_execution_result.trading_symbol,quantity=canonical_execution_result.quantity,lots=canonical_execution_result.lots,expected_pipeline_status=canonical_execution_result.pipeline_status,expected_execution_status=canonical_execution_result.execution_status,expected_fill_price=canonical_execution_result.fill_price,compared_observation_count=len(values))
 if not values:return PaperExecutionReplayResultV1(rid,now,"INCOMPLETE",blockers=("observations_missing",),**base)
 stages={v.stage for v in values}
 if canonical_execution_result.pipeline_status=="EXECUTED" and "EXECUTION" not in stages:return PaperExecutionReplayResultV1(rid,now,"INCOMPLETE",blockers=("execution_observation_missing",),**base)
 obs=next((v for v in values if v.stage=="PIPELINE_RESULT"),values[-1]); mismatches=[]
 for field in ("canonical_execution_result_id","execution_request_id","authorization_id","execution_result_id","idempotency_key","underlying_symbol","exchange","action","option_type","position_side","trading_symbol","quantity","lots"):
  expected=base.get(field); actual=getattr(obs,field)
  if expected is not None and actual is not None and expected!=actual:mismatches.append(field)
 observed_pipeline=obs.outcome if obs.stage=="PIPELINE_RESULT" else None;observed_execution=next((v.outcome for v in values if v.stage=="EXECUTION"),None);observed_fill=next((v.fill_price for v in values if v.stage=="EXECUTION"),None)
 base.update(observed_pipeline_status=observed_pipeline,observed_execution_status=observed_execution,observed_fill_price=observed_fill)
 if canonical_execution_result.pipeline_status=="EXECUTED" and (observed_execution!="EXECUTED" or observed_fill!=canonical_execution_result.fill_price):mismatches.append("execution_evidence")
 if mismatches:return PaperExecutionReplayResultV1(rid,now,"MISMATCHED",mismatched_fields=tuple(mismatches),matched_field_count=0,**base)
 return PaperExecutionReplayResultV1(rid,now,"MATCHED",matched_field_count=len(base),**base)

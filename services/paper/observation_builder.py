from datetime import datetime,timezone
from services.contracts.paper_execution_observation_v1 import PaperExecutionObservationV1
_ORDER=("RISK","CANDIDATE","REQUEST","AUTHORIZATION","EXECUTION","ORDER_STATE","PIPELINE_RESULT")
def _now(clock):
 value=(clock or (lambda:datetime.now(timezone.utc)))()
 if not isinstance(value,datetime) or value.tzinfo is None:raise ValueError("clock must return a timezone-aware datetime.")
 return value
def _value(obj,name,*alternatives):
 for key in (name,)+alternatives:
  if obj is not None and hasattr(obj,key):return getattr(obj,key)
 return None
def build_paper_execution_observations(*,canonical_risk_result=None,paper_candidate=None,execution_request=None,authorization=None,authorization_result=None,execution_result=None,order_state=None,canonical_execution_result=None,clock=None,observation_id_factory=None):
 supplied=(("RISK",canonical_risk_result),("CANDIDATE",paper_candidate),("REQUEST",execution_request),("AUTHORIZATION",authorization_result or authorization),("EXECUTION",execution_result),("ORDER_STATE",order_state),("PIPELINE_RESULT",canonical_execution_result)); now=_now(clock); observations=[]; factory=observation_id_factory or (lambda stage:f"observation:{stage}:{len(observations)}")
 identity=None
 for stage,obj in supplied:
  if obj is None:continue
  pair=(_value(obj,"underlying_symbol"),_value(obj,"exchange"))
  if pair!=(None,None):
   if identity is not None and pair!=identity:raise ValueError("Conflicting canonical market identity.")
   identity=pair
  outcome=(_value(obj,"pipeline_status") or _value(obj,"execution_status") or _value(obj,"authorization_status") or _value(obj,"order_status") or "RECORDED")
  outcome={"FILLED":"EXECUTED","AUTHORIZED":"AUTHORIZED","ACCEPTED":"APPROVED"}.get(outcome,outcome)
  if outcome not in {"APPROVED","NO_ACTION","BLOCKED","AUTHORIZED","EXECUTED","DUPLICATE","REJECTED","FAILED","RECORDED"}:outcome="RECORDED"
  kwargs={n:_value(obj,n) for n in PaperExecutionObservationV1.__dataclass_fields__ if n not in {"observation_id","observed_at","stage","outcome","blockers","warnings","schema_version","execution_mode","live_execution_eligible"}}
  kwargs["quantity"]=_value(obj,"quantity","requested_quantity");kwargs["lots"]=_value(obj,"lots","requested_lots");kwargs["capital_required"]=_value(obj,"capital_required","capital_used");kwargs["maximum_loss"]=_value(obj,"maximum_loss","realized_maximum_loss");kwargs["paper_order_id"]=_value(obj,"paper_order_id")
  kwargs["blockers"]=_value(obj,"blockers") or ();kwargs["warnings"]=_value(obj,"warnings") or ()
  if outcome in {"BLOCKED","REJECTED","FAILED"} and not kwargs["blockers"]:kwargs["blockers"]=("recorded_blocked_outcome",)
  observations.append(PaperExecutionObservationV1(factory(stage),_value(obj,"created_at","updated_at") or now,stage,outcome,**kwargs))
 return tuple(observations)

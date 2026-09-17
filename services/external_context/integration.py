"""Isolated deterministic orchestration for the four external-context evaluators."""
from __future__ import annotations
from datetime import datetime
from services.contracts.external_market_observation_v1 import ExternalMarketObservationV1
from services.contracts.institutional_flow_snapshot_v1 import InstitutionalFlowSnapshotV1
from services.contracts.scheduled_market_event_v1 import ScheduledMarketEventV1
from services.contracts.external_context_policy_v1 import DEFAULT_EXTERNAL_CONTEXT_POLICY,ExternalContextPolicyV1
from services.core.market_identity import normalize_market_identity
from importlib import import_module
from services.external_context.institutional import evaluate_institutional_flow_context
from services.external_context.events import evaluate_event_risk_context
from services.external_context.aggregate import evaluate_external_market_context
evaluate_global_market_context = import_module("services.external_context.global").evaluate_global_market_context
def evaluate_external_context_pipeline(*,underlying_symbol:str,exchange:str,observations:tuple[ExternalMarketObservationV1,...],institutional_snapshot:InstitutionalFlowSnapshotV1|None,scheduled_events:tuple[ScheduledMarketEventV1,...],policy:ExternalContextPolicyV1=DEFAULT_EXTERNAL_CONTEXT_POLICY,created_at:datetime,global_result_id:str,institutional_result_id:str,event_result_id:str,aggregate_result_id:str,global_evaluator=evaluate_global_market_context,institutional_evaluator=evaluate_institutional_flow_context,event_evaluator=evaluate_event_risk_context,aggregate_evaluator=evaluate_external_market_context):
 identity=normalize_market_identity(underlying_symbol,exchange)
 if identity is None:raise ValueError("unsupported market identity")
 if not isinstance(observations,tuple) or any(not isinstance(x,ExternalMarketObservationV1) for x in observations):raise TypeError("observations must be a tuple of ExternalMarketObservationV1")
 if institutional_snapshot is not None and not isinstance(institutional_snapshot,InstitutionalFlowSnapshotV1):raise TypeError("institutional_snapshot must be InstitutionalFlowSnapshotV1 or None")
 if not isinstance(scheduled_events,tuple) or any(not isinstance(x,ScheduledMarketEventV1) for x in scheduled_events):raise TypeError("scheduled_events must be a tuple of ScheduledMarketEventV1")
 if not isinstance(policy,ExternalContextPolicyV1):raise TypeError("policy must be ExternalContextPolicyV1")
 if not isinstance(created_at,datetime) or created_at.tzinfo is None or created_at.utcoffset() is None:raise ValueError("created_at must be timezone-aware")
 if any(not isinstance(v,str) or not v.strip() for v in (global_result_id,institutional_result_id,event_result_id,aggregate_result_id)):raise ValueError("result ids must be non-empty strings")
 if any(not callable(v) for v in (global_evaluator,institutional_evaluator,event_evaluator,aggregate_evaluator)):raise TypeError("evaluator dependencies must be callable")
 if len({x.canonical_name for x in observations})!=len(observations):raise ValueError("duplicate observation canonical names")
 if len({x.scheduled_market_event_id for x in scheduled_events})!=len(scheduled_events):raise ValueError("duplicate scheduled event ids")
 common=dict(underlying_symbol=identity[0],exchange=identity[1],policy=policy,created_at=created_at)
 global_context=global_evaluator(observations=observations,result_id=global_result_id,**common)
 institutional_context=institutional_evaluator(snapshot=institutional_snapshot,result_id=institutional_result_id,**common)
 event_context=event_evaluator(events=scheduled_events,result_id=event_result_id,**common)
 return aggregate_evaluator(global_context=global_context,institutional_context=institutional_context,event_context=event_context,result_id=aggregate_result_id,**common)

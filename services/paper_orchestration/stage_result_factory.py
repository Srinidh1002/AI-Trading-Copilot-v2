from __future__ import annotations
import hashlib
from datetime import datetime
from typing import Any
from services.contracts.paper_orchestration_failure_v1 import PaperOrchestrationFailureV1
from services.contracts.paper_orchestration_stage_result_v1 import PaperOrchestrationStageResultV1
def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime): raise TypeError(f'{name} must be a datetime')
    if value.tzinfo is None or value.utcoffset() is None: raise ValueError(f'{name} must be timezone-aware')
    return value
def _source_identity(value: object|None):
    if value is None: return None,None,None
    result_type=type(value).__name__; result_id=None
    for name in ('result_id','validation_id','opportunity_id','integration_id','paper_trade_id','portfolio_id','snapshot_id','decision_id'):
        candidate=getattr(value,name,None)
        if candidate is not None: result_id=str(candidate); break
    semantic_hash=None
    method=getattr(value,'semantic_hash',None)
    if callable(method): semantic_hash=str(method())
    else:
        to_json=getattr(value,'to_json',None)
        if callable(to_json): semantic_hash=hashlib.sha256(to_json().encode('utf-8')).hexdigest()
    return result_type,result_id,semantic_hash
def build_completed_stage_result(*,stage_result_id,cycle_id,stage,started_at,completed_at,source_result,paper_action_occurred=False,blockers=(),warnings=(),metadata=None,status='COMPLETED'):
    source_type,source_id,source_hash=_source_identity(source_result)
    return PaperOrchestrationStageResultV1(stage_result_id=stage_result_id,cycle_id=cycle_id,stage=stage,status=status,started_at=_aware(started_at,'started_at'),completed_at=_aware(completed_at,'completed_at'),source_result_type=source_type,source_result_id=source_id,source_semantic_hash=source_hash,paper_action_occurred=paper_action_occurred,blockers=blockers,warnings=warnings,metadata={} if metadata is None else metadata)
def build_failed_stage_result(*,stage_result_id,cycle_id,stage,started_at,completed_at,failure_code,message,retryable,source_component,exception=None,metadata=None):
    failure=PaperOrchestrationFailureV1(failure_code=failure_code,stage=stage,message=message,retryable=retryable,exception_type=None if exception is None else type(exception).__name__,source_component=source_component,metadata={} if metadata is None else metadata)
    return PaperOrchestrationStageResultV1(stage_result_id=stage_result_id,cycle_id=cycle_id,stage=stage,status='FAILED',started_at=_aware(started_at,'started_at'),completed_at=_aware(completed_at,'completed_at'),errors=(failure.failure_code,),failure=failure)

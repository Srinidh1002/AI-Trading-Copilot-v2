"""Deterministic replay coordinator; callers supply observations and IDs."""
from __future__ import annotations
from dataclasses import replace
from services.contracts import PaperTradePositionEvaluationInputV1
from .paper_trade_persistence_service import PaperTradePersistenceService
from .paper_trade_recovery_service import PaperTradeRecoveryService
from .paper_trade_position_evaluator import evaluate_open_paper_trade_position
class PaperTradeReplayCoordinator:
 def __init__(self,persistence_service):self.persistence_service=persistence_service;self.recovery_service=PaperTradeRecoveryService(persistence_service)
 def evaluate(self,snapshot,evaluation_input):
  if snapshot.lifecycle_state.is_terminal:raise ValueError('terminal snapshot cannot resume')
  if type(evaluation_input)is not PaperTradePositionEvaluationInputV1:raise TypeError('evaluation_input')
  if evaluation_input.position.position_id!=snapshot.position.position_id:raise ValueError('snapshot identity')
  result=evaluate_open_paper_trade_position(evaluation_input)
  if result.status=='BLOCKED' or result.position_decision=='BLOCK':return snapshot,result
  if result.pnl_evidence is None and result.position_decision=='HOLD':return snapshot,result
  updated=replace(snapshot,lifecycle_state=result.resulting_lifecycle_state,position=result.resulting_position,latest_observation=evaluation_input.observation,pnl_evidence=result.pnl_evidence,updated_at=evaluation_input.evaluation_timestamp,event_sequence=snapshot.event_sequence+1)
  self.persistence_service.save(updated);return updated,result

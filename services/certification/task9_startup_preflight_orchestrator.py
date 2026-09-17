"""Injected, fail-closed 12-phase Task 9 startup preflight orchestration."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Callable,Mapping
from services.contracts.task9_runtime_config_v1 import Task9RuntimeConfigV1
from services.contracts.task9_runtime_config_snapshot_v1 import Task9RuntimeConfigSnapshotV1,task9_runtime_config_content_sha256
from services.contracts.task9_startup_preflight_v1 import *
from services.contracts.task9_startup_failure_semantics_v1 import *
from services.contracts.task9_provider_capability_report_v1 import Task9ProviderCapabilityReportV1
from services.certification.task9_provider_capability_report_builder import build_task9_provider_capability_preflight_phases

class Task9StartupPreflightMode(str,Enum): OFFLINE_BUILD_VALIDATION="OFFLINE_BUILD_VALIDATION"; LIVE_CERTIFICATION_STARTUP="LIVE_CERTIFICATION_STARTUP"
def _pass(phase,at,code):return Task9StartupPreflightPhaseResultV1(phase,Task9StartupPreflightPhaseStatus.PASS,False,code,None,at)
def _notrun(phase,at):return Task9StartupPreflightPhaseResultV1(phase,Task9StartupPreflightPhaseStatus.NOT_RUN,False,"PREVIOUS_PHASE_BLOCKED",None,at)
class Task9StartupPreflightOrchestrator:
 def __init__(self,*,runtime_config:Task9RuntimeConfigV1,snapshot:Task9RuntimeConfigSnapshotV1,capability_report:Task9ProviderCapabilityReportV1,mode:Task9StartupPreflightMode|str,checks:Mapping[Task9StartupPreflightPhase,Callable[[],Task9StartupPreflightPhaseResultV1]]|None=None):
  if type(runtime_config)is not Task9RuntimeConfigV1 or type(snapshot)is not Task9RuntimeConfigSnapshotV1 or type(capability_report)is not Task9ProviderCapabilityReportV1:raise TypeError("preflight authority")
  self.runtime_config,self.snapshot,self.capability_report=runtime_config,snapshot,capability_report
  self.mode=Task9StartupPreflightMode(mode);self.checks=dict(checks or {})
  if any(not isinstance(k,Task9StartupPreflightPhase) or not callable(v) for k,v in self.checks.items()):raise TypeError("checks")
 def _default(self,phase,at):
  c=self.runtime_config
  if phase is Task9StartupPreflightPhase.STATIC_CONFIG_VALIDATION:return _pass(phase,at,"STATIC_CONFIG_VALID")
  if phase is Task9StartupPreflightPhase.PAPER_SAFETY:
   if c.execution_mode!="PAPER" or c.broker_order_submission or c.live_execution_eligible:return build_task9_startup_phase_result(phase=phase,reason_code=Task9StartupReasonCode.NON_PAPER_MODE,observed_at=at)
   return _pass(phase,at,"PAPER_SAFETY_VALID")
  if phase is Task9StartupPreflightPhase.MARKET_SESSION_IDENTITY:return _pass(phase,at,"MARKET_SESSION_IDENTITY_VALID")
  if phase in {Task9StartupPreflightPhase.REQUIRED_ANGEL_CAPABILITY_READINESS,Task9StartupPreflightPhase.OPTIONAL_PROVIDER_CAPABILITY_STATE}:return build_task9_provider_capability_preflight_phases(self.capability_report,observed_at=at)[0 if phase is Task9StartupPreflightPhase.REQUIRED_ANGEL_CAPABILITY_READINESS else 1]
  if phase is Task9StartupPreflightPhase.REPRODUCIBILITY_SNAPSHOT:
   if self.snapshot.runtime_config_id!=c.runtime_config_id or self.snapshot.content_sha256!=task9_runtime_config_content_sha256(c):return build_task9_startup_phase_result(phase=phase,reason_code=Task9StartupReasonCode.SNAPSHOT_HASH_MISMATCH,observed_at=at)
   return _pass(phase,at,"REPRODUCIBILITY_SNAPSHOT_VALID")
  reason={Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY:Task9StartupReasonCode.ACTIVE_AUTHORITY_UNAVAILABLE,Task9StartupPreflightPhase.PERSISTENCE_INTEGRITY_WRITABILITY:Task9StartupReasonCode.PERSISTENCE_UNAVAILABLE,Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION:Task9StartupReasonCode.AB1011,Task9StartupPreflightPhase.COLLECTOR_RUNTIME_READINESS:Task9StartupReasonCode.COLLECTOR_NOT_READY,Task9StartupPreflightPhase.DASHBOARD_ACTIVE_CAMPAIGN_AUTHORITY:Task9StartupReasonCode.ACTIVE_AUTHORITY_UNAVAILABLE}[phase]
  return build_task9_startup_phase_result(phase=phase,reason_code=reason,observed_at=at)
 def run(self,*,preflight_id:str,observed_at:datetime)->Task9StartupPreflightResultV1:
  results=[];blocked=False
  for phase in tuple(Task9StartupPreflightPhase)[:-1]:
   if blocked:results.append(_notrun(phase,observed_at));continue
   result=self.checks[phase]() if phase in self.checks else self._default(phase,observed_at)
   if type(result)is not Task9StartupPreflightPhaseResultV1 or result.phase is not phase:raise ValueError("phase check result")
   results.append(result);blocked=result.blocking
  final=Task9StartupPreflightPhase.FINAL_LAUNCH_APPROVAL
  if blocked or self.mode is Task9StartupPreflightMode.OFFLINE_BUILD_VALIDATION:results.append(_notrun(final,observed_at))
  else:results.append(_pass(final,observed_at,"FINAL_LAUNCH_APPROVED"))
  return Task9StartupPreflightResultV1(preflight_id,self.snapshot.snapshot_id,self.snapshot.content_sha256,self.runtime_config.campaign_id,self.runtime_config.market_date,self.runtime_config.official_run_id,self.runtime_config.run_classification,observed_at,observed_at,tuple(results))

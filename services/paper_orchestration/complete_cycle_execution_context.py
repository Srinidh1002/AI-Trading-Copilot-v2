from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from services.contracts.paper_orchestration_cycle_input_v1 import PaperOrchestrationCycleInputV1
from services.paper_orchestration.new_entry_paper_lifecycle_executor import NewEntryPaperLifecycleInputV1
from services.paper_orchestration.p6_planning_stage_executor import P6PlanningStageInputV1
@runtime_checkable
class DataStageAuthority(Protocol):
    def __call__(self, cycle_input: PaperOrchestrationCycleInputV1) -> object: ...
@runtime_checkable
class SessionStageAuthority(Protocol):
    def __call__(self, cycle_input: PaperOrchestrationCycleInputV1, data_result: object) -> object: ...
@runtime_checkable
class AnalysisStageAuthority(Protocol):
    def __call__(self, cycle_input: PaperOrchestrationCycleInputV1, data_result: object, session_result: object) -> object: ...
@runtime_checkable
class OpportunityStageAuthority(Protocol):
    def __call__(self, cycle_input: PaperOrchestrationCycleInputV1, analysis_result: object, session_result: object) -> object: ...
@runtime_checkable
class P6InputFactory(Protocol):
    def __call__(self, cycle_input: PaperOrchestrationCycleInputV1, analysis_result: object, opportunity_result: object) -> P6PlanningStageInputV1: ...
@runtime_checkable
class NewEntryInputFactory(Protocol):
    def __call__(self, cycle_input: PaperOrchestrationCycleInputV1, integrated_trade_plan_result: object) -> NewEntryPaperLifecycleInputV1: ...
@dataclass(frozen=True, slots=True)
class CompleteCycleAuthoritySetV1:
    data_authority: DataStageAuthority
    session_authority: SessionStageAuthority
    analysis_authority: AnalysisStageAuthority
    opportunity_authority: OpportunityStageAuthority
    p6_input_factory: P6InputFactory
    new_entry_input_factory: NewEntryInputFactory
    execution_mode: str = 'PAPER'
    live_execution_eligible: bool = False
    schema_version: str = 'complete_cycle_authority_set.v1'
    def __post_init__(self):
        for name in ('data_authority','session_authority','analysis_authority','opportunity_authority','p6_input_factory','new_entry_input_factory'):
            if not callable(getattr(self,name)): raise TypeError(f'{name} must be callable')
        if self.execution_mode!='PAPER': raise ValueError('execution_mode must be PAPER')
        if self.live_execution_eligible: raise ValueError('live execution is not eligible')
        if self.schema_version!='complete_cycle_authority_set.v1': raise ValueError('unsupported schema_version')
@dataclass(frozen=True, slots=True)
class PaperOrchestrationExecutionContextV1:
    cycle_input: PaperOrchestrationCycleInputV1
    authorities: CompleteCycleAuthoritySetV1
    execution_mode: str = 'PAPER'
    live_execution_eligible: bool = False
    schema_version: str = 'paper_orchestration_execution_context.v1'
    def __post_init__(self):
        if type(self.cycle_input) is not PaperOrchestrationCycleInputV1: raise TypeError('cycle_input must be exact PaperOrchestrationCycleInputV1')
        if type(self.authorities) is not CompleteCycleAuthoritySetV1: raise TypeError('authorities must be exact CompleteCycleAuthoritySetV1')
        if self.execution_mode!='PAPER': raise ValueError('execution_mode must be PAPER')
        if self.live_execution_eligible: raise ValueError('live execution is not eligible')
        if self.schema_version!='paper_orchestration_execution_context.v1': raise ValueError('unsupported schema_version')

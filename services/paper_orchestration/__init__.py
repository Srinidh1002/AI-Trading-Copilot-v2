"""P9 real-time PAPER orchestration package.

This package is PAPER-only and must never import live broker order execution.
"""

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_orchestration_failure_v1 import (
    PaperOrchestrationFailureV1,
)
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.contracts.paper_orchestration_stage_result_v1 import (
    PaperOrchestrationStageResultV1,
)

from services.paper_orchestration.deterministic_cycle_coordinator import (
    DeterministicPaperOrchestrationCycleCoordinator,
)

from services.paper_orchestration.paper_state_factories import (
    build_entry_paper_trade_persistence_snapshot,
    build_initial_paper_portfolio_snapshot,
    build_initial_paper_trade_lifecycle_state,
)

from services.paper_orchestration.p6_planning_stage_executor import (
    P6PlanningStageInputV1,
    execute_p6_planning_stage,
)

from services.paper_orchestration.new_entry_paper_lifecycle_executor import (
    NewEntryPaperLifecycleExecutor,
    NewEntryPaperLifecycleInputV1,
    NewEntryPaperLifecycleResultV1,
)

from services.paper_orchestration.complete_cycle_execution_context import (
    CompleteCycleAuthoritySetV1,
    PaperOrchestrationExecutionContextV1,
)
from services.paper_orchestration.stage_result_factory import (
    build_completed_stage_result,
    build_failed_stage_result,
)

from services.paper_orchestration.complete_cycle_executor import (
    CompletePaperOrchestrationCycleExecutor,
)

from services.paper_orchestration.existing_position_monitoring_executor import (
    ExistingPositionMonitoringExecutor,
    ExistingPositionMonitoringInputV1,
    ExistingPositionMonitoringResultV1,
)

from services.paper_orchestration.existing_position_monitoring_cycle_executor import (
    ExistingPositionMonitoringCycleExecutor,
)

from services.paper_orchestration.continuous_runtime_adapter import (
    ContinuousPaperOrchestrationRuntimeAdapter,
    ContinuousPaperOrchestrationRuntimeConfigV1,
)
from services.paper_orchestration.restart_recovery_operation import (
    RestartRecoveryOperation,
    RestartRecoveryTargetV1,
)

__all__ = [
    "ContinuousPaperOrchestrationRuntimeAdapter",
    "ContinuousPaperOrchestrationRuntimeConfigV1",
    "RestartRecoveryOperation",
    "RestartRecoveryTargetV1",
    "ExistingPositionMonitoringCycleExecutor",
    "ExistingPositionMonitoringExecutor",
    "ExistingPositionMonitoringInputV1",
    "ExistingPositionMonitoringResultV1",
    "CompletePaperOrchestrationCycleExecutor",
    "CompleteCycleAuthoritySetV1",
    "PaperOrchestrationExecutionContextV1",
    "build_completed_stage_result",
    "build_failed_stage_result",
    "NewEntryPaperLifecycleExecutor",
    "NewEntryPaperLifecycleInputV1",
    "NewEntryPaperLifecycleResultV1",
    "P6PlanningStageInputV1",
    "execute_p6_planning_stage",
    "build_initial_paper_portfolio_snapshot",
    "build_initial_paper_trade_lifecycle_state",
    "build_entry_paper_trade_persistence_snapshot",
    "DeterministicPaperOrchestrationCycleCoordinator",
    "PaperOrchestrationCycleInputV1",
    "PaperOrchestrationCycleResultV1",
    "PaperOrchestrationFailureV1",
    "PaperOrchestrationPolicyV1",
    "PaperOrchestrationStageResultV1",
]

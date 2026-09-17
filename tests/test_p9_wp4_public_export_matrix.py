import services.paper_orchestration as paper_orchestration

EXPECTED_EXPORTS = {
    "CompleteCycleAuthoritySetV1",
    "CompletePaperOrchestrationCycleExecutor",
    "ContinuousPaperOrchestrationRuntimeAdapter",
    "ContinuousPaperOrchestrationRuntimeConfigV1",
    "DeterministicPaperOrchestrationCycleCoordinator",
    "ExistingPositionMonitoringCycleExecutor",
    "ExistingPositionMonitoringExecutor",
    "ExistingPositionMonitoringInputV1",
    "ExistingPositionMonitoringResultV1",
    "NewEntryPaperLifecycleExecutor",
    "NewEntryPaperLifecycleInputV1",
    "NewEntryPaperLifecycleResultV1",
    "P6PlanningStageInputV1",
    "PaperOrchestrationCycleInputV1",
    "PaperOrchestrationCycleResultV1",
    "PaperOrchestrationExecutionContextV1",
    "PaperOrchestrationFailureV1",
    "PaperOrchestrationPolicyV1",
    "PaperOrchestrationStageResultV1",
    "RestartRecoveryOperation",
    "RestartRecoveryTargetV1",
    "build_completed_stage_result",
    "build_entry_paper_trade_persistence_snapshot",
    "build_failed_stage_result",
    "build_initial_paper_portfolio_snapshot",
    "build_initial_paper_trade_lifecycle_state",
    "execute_p6_planning_stage",
}

def test_required_p9_public_exports_are_present():
    assert EXPECTED_EXPORTS.issubset(set(paper_orchestration.__all__))

def test_all_declared_exports_resolve():
    for name in paper_orchestration.__all__:
        assert hasattr(paper_orchestration, name), name

def test_public_exports_do_not_expose_live_execution_symbols():
    forbidden = ("broker", "live_market_engine", "order_executor", "order_manager", "place_order")
    for name in paper_orchestration.__all__:
        lowered = name.lower()
        assert not any(fragment in lowered for fragment in forbidden), name

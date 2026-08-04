from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")

def test_complete_cycle_executor_contains_locked_new_entry_order():
    source = read("services/paper_orchestration/complete_cycle_executor.py")
    tokens = (
        'stage="DATA"',
        'stage="SESSION"',
        'stage="ANALYSIS"',
        'stage="OPPORTUNITY"',
        'stage="P6_PLAN"',
        'stage="P8_ADMISSION"',
        'stage="P7_LIFECYCLE"',
        'stage="P8_PORTFOLIO_UPDATE"',
    )
    offsets = tuple(source.index(token) for token in tokens)
    assert offsets == tuple(sorted(offsets))

def test_monitoring_cycle_projects_p7_before_p8():
    source = read("services/paper_orchestration/existing_position_monitoring_cycle_executor.py")
    assert source.index('stage="P7_LIFECYCLE"') < source.index('stage="P8_PORTFOLIO_UPDATE"')

def test_deterministic_coordinator_owns_outer_journal_boundary():
    source = read("services/paper_orchestration/deterministic_cycle_coordinator.py")
    classification = source.index("self.journal.classify(")
    execution = source.index("self.cycle_executor(cycle_input)")
    save = source.index("self.journal.save(")
    assert classification < execution < save

def test_runtime_adapter_orders_opportunity_before_monitoring():
    source = read("services/paper_orchestration/continuous_runtime_adapter.py")
    opportunity = source.index("opportunity_cycle=self._run_opportunity_cycle")
    monitoring = source.index("monitoring_cycle=self._run_monitoring_cycle")
    assert opportunity < monitoring

def test_restart_recovery_is_fail_closed_for_any_target():
    source = read("services/paper_orchestration/restart_recovery_operation.py")
    assert "success = True" in source
    assert "success = success and item_success" in source
    assert "except Exception as exc:" in source
    assert '"success": False' in source

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "P10_WP2_P6_P7_FIELD_AUDIT.md"
DESIGN = ROOT / "docs" / "P10_WP2_PROJECTION_DESIGN.md"


def test_audit_records_actual_orchestration_files():
    source = AUDIT.read_text(encoding="utf-8")

    assert "p6_planning_stage_executor.py" in source
    assert "new_entry_paper_lifecycle_executor.py" in source
    assert "complete_opportunity_cycle_executor.py" in source
    assert "must not require or invent it" in source


def test_audit_names_authoritative_p6_contracts():
    source = AUDIT.read_text(encoding="utf-8")

    for name in (
        "TradeOpportunityV1",
        "ThreeTargetTradePlanV1",
        "IntegratedThreeTargetTradePlanResultV1",
    ):
        assert name in source


def test_audit_names_authoritative_p7_contracts():
    source = AUDIT.read_text(encoding="utf-8")

    for name in (
        "PaperTradeLifecycleStateV1",
        "PaperTradePositionV1",
        "PaperTradeFillV1",
        "PaperTradePnlEvidenceV1",
        "PaperTradePersistenceSnapshotV1",
    ):
        assert name in source


def test_audit_records_plan_fields():
    source = AUDIT.read_text(encoding="utf-8")

    for field in (
        "entry_zone_lower",
        "entry_zone_upper",
        "stop_loss_price",
        "target_1",
        "target_2",
        "target_3",
        "lot_count",
        "quantity",
        "required_capital",
        "risk_amount",
        "maximum_permissible_loss",
        "estimated_total_charges",
        "expiry",
    ):
        assert f"`{field}`" in source


def test_audit_records_position_and_pnl_fields():
    source = AUDIT.read_text(encoding="utf-8")

    for field in (
        "remaining_quantity",
        "exit_fills",
        "realized_net_pnl",
        "unrealized_pnl",
        "total_pnl",
        "realized_net_pnl_after",
        "unrealized_pnl_after",
        "total_pnl_after",
    ):
        assert f"`{field}`" in source


def test_audit_records_all_canonical_lifecycle_states():
    source = AUDIT.read_text(encoding="utf-8")

    for state in (
        "PLANNED",
        "WAITING_FOR_ENTRY",
        "OPEN",
        "PARTIALLY_EXITED",
        "CLOSED_TARGET_1",
        "CLOSED_TARGET_2",
        "CLOSED_TARGET_3",
        "CLOSED_STOP",
        "CLOSED_INVALIDATED",
        "CLOSED_SESSION",
        "CLOSED_EXPIRY",
        "CANCELLED",
        "BLOCKED",
    ):
        assert f"`{state}`" in source


def test_projection_design_is_paper_only_and_noncomputational():
    source = DESIGN.read_text(encoding="utf-8")

    assert "execution_mode == \"PAPER\"" in source
    assert "live_execution_eligible is False" in source
    assert "must not sum fill cash effects to recreate P&L" in source
    assert "must not make trading decisions" in source

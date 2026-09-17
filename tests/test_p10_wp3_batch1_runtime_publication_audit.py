from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "P10_WP3_RUNTIME_PUBLICATION_AUDIT.md"
DESIGN = ROOT / "docs" / "P10_WP3_PUBLICATION_DESIGN.md"
RUNTIME = ROOT / "services" / "continuous_paper_trading_runtime.py"
CYCLE_INPUT = (
    ROOT
    / "services"
    / "contracts"
    / "paper_orchestration_cycle_input_v1.py"
)
CYCLE_EXECUTOR = (
    ROOT
    / "services"
    / "paper_orchestration"
    / "complete_cycle_executor.py"
)


def test_audit_records_actual_repository_paths():
    source = AUDIT.read_text(encoding="utf-8")

    assert "complete_cycle_executor.py" in source
    assert "services/contracts/paper_orchestration_cycle_input_v1.py" in source
    assert "previously assumed alternative filenames" in source


def test_runtime_retains_last_cycle_operation_results():
    source = RUNTIME.read_text(encoding="utf-8")

    assert '"last_cycle": None' in source
    assert 'self._stats[\n                "last_cycle"\n            ]' in source
    assert '"opportunity": (' in source
    assert '"monitoring": (' in source
    assert 'return deepcopy(\n                cycle_report\n            )' in source


def test_runtime_get_stats_is_defensive():
    source = RUNTIME.read_text(encoding="utf-8")

    assert "result = deepcopy(" in source
    assert "return result" in source


def test_cycle_input_carries_optional_publication_sources():
    source = CYCLE_INPUT.read_text(encoding="utf-8")

    for field in (
        "trade_opportunity",
        "integrated_trade_plan_result",
        "p7_persistence_snapshot",
        "p8_persistence_snapshot",
    ):
        assert field in source


def test_cycle_executor_has_typed_intermediate_results():
    source = CYCLE_EXECUTOR.read_text(encoding="utf-8")

    for token in (
        "opportunity_result",
        "p6_result",
        "lifecycle_result",
        "NewEntryPaperLifecycleResultV1",
    ):
        assert token in source
def test_lifecycle_result_contract_exposes_p7_and_p8_snapshots():
    lifecycle_executor = (
        ROOT
        / "services"
        / "paper_orchestration"
        / "new_entry_paper_lifecycle_executor.py"
    )
    source = lifecycle_executor.read_text(encoding="utf-8")

    assert "p7_snapshot: PaperTradePersistenceSnapshotV1 | None" in source
    assert "p8_snapshot: PaperPortfolioPersistenceSnapshotV1 | None" in source


def test_audit_selects_thread_safe_last_known_good_store():
    source = AUDIT.read_text(encoding="utf-8")

    assert "thread-safe publication store" in source
    assert "last-known-good" in source
    assert "transient failure must not clear" in source
    assert "publication store therefore needs its own lock" in source


def test_design_forbids_hidden_runtime_or_ui_authority():
    source = DESIGN.read_text(encoding="utf-8")

    for text in (
        "no direct Streamlit dependency",
        "no direct persistence dependency",
        "no business computation",
        "no clearing last-known-good state on failure",
    ):
        assert text in source

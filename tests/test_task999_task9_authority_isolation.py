"""Task 9.99 official authority-isolation certification."""

from pathlib import Path


LAUNCHER = Path(
    "services/certification/"
    "task9_live_paper_certification_launcher.py"
)

PRODUCTION_COMPOSITION = Path(
    "services/certification/"
    "task9_live_paper_production_composition.py"
)

CHILD_AUTHORITY = Path(
    "services/certification/"
    "task9_production_child_evidence_authority.py"
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_official_task9_launcher_does_not_import_task8_composition():
    source = _source(LAUNCHER)

    forbidden = (
        "task8_live_paper_default_composition",
        "build_task8_dependencies",
        "task8_dependencies_factory",
        "_build_task8_dependencies",
    )

    for value in forbidden:
        assert value not in source


def test_official_task9_launcher_does_not_invoke_task8_lifecycle():
    source = _source(LAUNCHER)

    forbidden = (
        "task8_selected_market_lifecycle_runtime",
        "execute_task8_selected_market_lifecycle",
        "task8_selected_market_p6_bundle",
        "build_task8_selected_market_p6_bundle",
    )

    for value in forbidden:
        assert value not in source


def test_task9_production_runtime_has_no_task8_composition_authority():
    source = _source(PRODUCTION_COMPOSITION)

    forbidden = (
        "task8_live_paper_default_composition",
        "build_task8_dependencies",
        "task8_selected_market_lifecycle_runtime",
        "execute_task8_selected_market_lifecycle",
        "task8_selected_market_p6_bundle",
        "build_task8_selected_market_p6_bundle",
    )

    for value in forbidden:
        assert value not in source


def test_task9_child_authority_has_no_task8_composition_authority():
    source = _source(CHILD_AUTHORITY)

    forbidden = (
        "task8_live_paper_default_composition",
        "build_task8_dependencies",
        "task8_selected_market_lifecycle_runtime",
        "execute_task8_selected_market_lifecycle",
        "task8_selected_market_p6_bundle",
        "build_task8_selected_market_p6_bundle",
    )

    for value in forbidden:
        assert value not in source


def test_task9_production_runtime_remains_paper_only():
    source = _source(PRODUCTION_COMPOSITION)

    assert 'execution_mode: str = "PAPER"' in source
    assert "broker_order_submission: bool = False" in source
    assert "live_execution_eligible: bool = False" in source


def test_task9_child_authority_uses_exact_task9_handoff():
    source = _source(CHILD_AUTHORITY)

    assert "Task9CycleMarketEvidenceV1" in source
    assert "cycle_evidence_by_market" in source
    assert "_freeze_handoffs(" in source


TASK9_SELECTED_LIFECYCLE = Path(
    "services/certification/"
    "task9_selected_market_lifecycle_composition.py"
)


def test_task9_selected_lifecycle_does_not_delegate_to_task8_lifecycle():
    source = _source(TASK9_SELECTED_LIFECYCLE)

    forbidden = (
        "task8_selected_market_lifecycle_runtime",
        "execute_task8_selected_market_lifecycle",
    )

    for value in forbidden:
        assert value not in source


def test_official_task9_graph_has_no_task8_p6_bundle_authority():
    paths = (
        LAUNCHER,
        PRODUCTION_COMPOSITION,
        CHILD_AUTHORITY,
        TASK9_SELECTED_LIFECYCLE,
    )

    forbidden = (
        "task8_selected_market_p6_bundle",
        "build_task8_selected_market_p6_bundle",
    )

    for path in paths:
        source = _source(path)
        for value in forbidden:
            assert value not in source


TASK9_P6_AUTHORITY = Path(
    "services/trade_planning/"
    "task9_selected_market_p6_bundle.py"
)


def test_task9_selected_p6_authority_is_task9_owned():
    source = _source(TASK9_P6_AUTHORITY)

    required = (
        "build_task9_selected_market_p6_bundle",
        'target_method="DEPLOYED_CAPITAL_RETURN"',
        "target_1_multiplier=0.15",
        "target_2_multiplier=0.30",
        "target_3_multiplier=0.50",
        "calculate_task9_local_paper_cost_evidence",
        'policy_source="TASK9_LOCAL_FIXED_ASSUMPTION_MODEL"',
    )

    for value in required:
        assert value in source

    forbidden = (
        "Task 8",
        "TASK8",
        "task8",
        "build_task8_selected_market_p6_bundle",
    )

    for value in forbidden:
        assert value not in source


TASK9_CANDIDATE_ADAPTER = Path(
    "services/certification/"
    "task9_live_candidate_adapter.py"
)


def test_task9_candidate_adapter_has_no_task8_or_legacy_strategy_authority():
    source = _source(TASK9_CANDIDATE_ADAPTER)

    required = (
        "build_task9_retaining_candidate_reader",
        "evaluate_task9_live_candidate",
        "evaluate_captured_certified_market_candidate",
        "allow_legacy_fallback=False",
        "CANONICAL_POLICY_UNAVAILABLE",
    )

    for value in required:
        assert value in source

    forbidden = (
        "Task 8",
        "TASK8",
        "task8",
        "Task8",
        "allow_legacy_fallback=True",
        "strategy_direction",
        "strategy_decision",
        "strategy_confidence",
        "strategy_score",
        "Migration/shadow mode only",
    )

    for value in forbidden:
        assert value not in source



def test_official_task9_graph_has_no_forbidden_execution_or_legacy_authority():
    paths = (
        Path(
            "services/certification/"
            "task9_live_paper_certification_launcher.py"
        ),
        Path(
            "services/certification/"
            "task9_parent_evidence_composition.py"
        ),
        Path(
            "services/certification/"
            "task9_selected_market_lifecycle_composition.py"
        ),
        Path(
            "services/certification/"
            "task9_selected_market_lifecycle_runtime.py"
        ),
    )

    forbidden = (
        "services.execution.order_executor",
        "services.execution.order_tracker",
        "placeOrder",
        "modifyOrder",
        "cancelOrder",
        "SmartWebSocketOrderUpdate",
        "allow_legacy_fallback=True",
        "strategy_direction",
        "strategy_decision",
        "strategy_confidence",
        "strategy_score",
    )

    source = "\n".join(
        _source(path)
        for path in paths
    )

    for value in forbidden:
        assert value not in source


def test_official_task9_launcher_injects_zero_rest_timeframe_provider():
    launcher = Path(
        "services/certification/"
        "task9_live_paper_certification_launcher.py"
    )
    source = _source(launcher)

    required = (
        "build_task9_precomposed_timeframe_provider",
        "fallback_factory",
        "precomposed_timeframe_provider_factory=fallback_factory",
    )

    for value in required:
        assert value in source

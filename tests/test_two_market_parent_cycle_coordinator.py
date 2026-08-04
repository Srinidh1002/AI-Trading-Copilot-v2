"""Task 3 Slice 3 exact-once parent coordinator certification."""
from dataclasses import replace
import ast
from pathlib import Path

import pytest

from services.contracts.two_market_decision_policy_v1 import (
    TwoMarketDecisionPolicyV1,
)
from services.contracts.two_market_parent_cycle_input_v1 import (
    TwoMarketParentCycleInputV1,
)
from services.paper_orchestration.two_market_parent_cycle_coordinator import (
    run_two_market_parent_cycle,
)
from test_market_analysis_candidate_v1 import build


def parent():
    sample = build(underlying_symbol="NIFTY")
    return TwoMarketParentCycleInputV1(
        parent_cycle_id="parent-1",
        decision_result_id="decision-1",
        nifty_child_result_id="child-NIFTY",
        sensex_child_result_id="child-SENSEX",
        nifty_observation_id="observation-NIFTY",
        sensex_observation_id="observation-SENSEX",
        requested_at=sample.requested_at,
        completed_at=sample.received_at,
        decision_policy=TwoMarketDecisionPolicyV1(180.0, 5.0),
    )


def candidate_for(symbol, observation_id, **changes):
    value = build(underlying_symbol=symbol)
    return replace(
        value,
        observation_id=observation_id,
        **changes,
    )


def test_parent_evaluates_each_market_exactly_once_and_selects_at_most_one():
    calls = []

    def evaluator(symbol, exchange, observation_id):
        calls.append((symbol, exchange, observation_id))
        return candidate_for(
            symbol,
            observation_id,
            score=80.0 if symbol == "NIFTY" else 60.0,
        )

    result = run_two_market_parent_cycle(
        parent(),
        child_evaluator=evaluator,
    )

    assert calls == [
        ("NIFTY", "NSE", "observation-NIFTY"),
        ("SENSEX", "BSE", "observation-SENSEX"),
    ]
    assert result.selected_market == ("NIFTY", "NSE")
    assert len(result.entries) == 2
    assert sum(
        entry.outcome_reason == "SELECTED"
        for entry in result.entries
    ) == 1


def test_one_market_failure_retains_other_terminal_result_and_can_select_it():
    calls = []

    def evaluator(symbol, exchange, observation_id):
        calls.append(symbol)
        if symbol == "NIFTY":
            raise RuntimeError("INJECTED_NIFTY_FAILURE")
        return candidate_for(
            symbol,
            observation_id,
            score=65.0,
        )

    result = run_two_market_parent_cycle(
        parent(),
        child_evaluator=evaluator,
    )

    assert calls == ["NIFTY", "SENSEX"]
    assert result.selected_market == ("SENSEX", "BSE")
    assert result.entries[0].child.terminal_status == "FAILED"
    assert result.entries[0].outcome_reason == "CHILD_FAILED"
    assert result.entries[1].child.terminal_status == "COMPLETED"


def test_both_fail_produces_no_trade_and_retains_both_failures():
    calls = []

    def evaluator(symbol, exchange, observation_id):
        calls.append(symbol)
        raise RuntimeError(f"{symbol}_FAILURE")

    result = run_two_market_parent_cycle(
        parent(),
        child_evaluator=evaluator,
    )

    assert calls == ["NIFTY", "SENSEX"]
    assert result.decision == "NO_TRADE"
    assert result.selected_market is None
    assert tuple(
        entry.child.terminal_status for entry in result.entries
    ) == ("FAILED", "FAILED")


def test_wrong_candidate_identity_fails_only_that_child():
    def evaluator(symbol, exchange, observation_id):
        if symbol == "NIFTY":
            return candidate_for("SENSEX", observation_id)
        return candidate_for(symbol, observation_id)

    result = run_two_market_parent_cycle(
        parent(),
        child_evaluator=evaluator,
    )

    assert result.entries[0].child.terminal_status == "FAILED"
    assert result.entries[1].child.terminal_status == "COMPLETED"
    assert result.selected_market == ("SENSEX", "BSE")


def test_non_candidate_return_fails_only_that_child():
    def evaluator(symbol, exchange, observation_id):
        if symbol == "NIFTY":
            return {}
        return candidate_for(symbol, observation_id)

    result = run_two_market_parent_cycle(
        parent(),
        child_evaluator=evaluator,
    )

    assert result.entries[0].child.terminal_status == "FAILED"
    assert result.entries[1].child.terminal_status == "COMPLETED"


def test_neither_candidate_eligible_produces_no_trade():
    def evaluator(symbol, exchange, observation_id):
        return candidate_for(
            symbol,
            observation_id,
            eligibility="INELIGIBLE",
            direction="NEUTRAL",
            score=0.0,
            confidence=0.0,
            blockers=(f"{symbol}_BLOCKED",),
        )

    result = run_two_market_parent_cycle(
        parent(),
        child_evaluator=evaluator,
    )

    assert result.decision == "NO_TRADE"
    assert tuple(
        entry.outcome_reason for entry in result.entries
    ) == ("INELIGIBLE", "INELIGIBLE")


def test_parent_input_rejects_duplicate_child_or_observation_ids():
    value = parent()
    with pytest.raises(ValueError, match="child result IDs"):
        replace(
            value,
            sensex_child_result_id=value.nifty_child_result_id,
        )
    with pytest.raises(ValueError, match="observation IDs"):
        replace(
            value,
            sensex_observation_id=value.nifty_observation_id,
        )


def test_coordinator_has_no_four_market_planning_or_execution_dependencies():
    source = Path(
        "services/paper_orchestration/"
        "two_market_parent_cycle_coordinator.py"
    ).read_text(encoding="utf-8")
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = (
        "four_market",
        "market_ranking_engine",
        "opportunity_ranking",
        "trade_planning",
        "paper_trading",
        "paper_portfolio",
        "broker",
        "dashboard",
    )
    assert not any(
        any(token in module for token in forbidden)
        for module in imports
    )
    for token in (
        "place_order(",
        "submit_order(",
        "random.",
        "datetime.now(",
        "datetime.utcnow(",
        "uuid4(",
        "time.sleep(",
    ):
        assert token not in source

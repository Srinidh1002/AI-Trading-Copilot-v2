"""Task 3A selected-market planner handoff certification."""
from dataclasses import replace
from datetime import timedelta
import ast
from pathlib import Path

import pytest

from services.trade_planning.selected_market_planning_bridge import (
    bridge_selected_market_to_planning,
)
from services.contracts.selected_market_planning_bridge_result_v1 import (
    SelectedMarketPlanningBridgeResultV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionEntryV1,
    TwoMarketDecisionResultV1,
)
from services.contracts.two_market_child_terminal_result_v1 import (
    TwoMarketChildTerminalResultV1,
)
from test_market_analysis_candidate_v1 import build


def child(symbol, **changes):
    candidate = replace(
        build(underlying_symbol=symbol),
        **changes,
    )
    return TwoMarketChildTerminalResultV1(
        child_result_id=f"child-{symbol}",
        parent_cycle_id="parent-1",
        observation_id=candidate.observation_id,
        underlying_symbol=candidate.underlying_symbol,
        exchange=candidate.exchange,
        requested_at=candidate.requested_at,
        received_at=candidate.received_at,
        terminal_status="COMPLETED",
        candidate=candidate,
    )


def selected_decision(
    *,
    selected_symbol="NIFTY",
    selected_changes=None,
):
    selected_changes = selected_changes or {}
    nifty = child(
        "NIFTY",
        score=80.0 if selected_symbol == "NIFTY" else 60.0,
        **(selected_changes if selected_symbol == "NIFTY" else {}),
    )
    sensex = child(
        "SENSEX",
        score=80.0 if selected_symbol == "SENSEX" else 60.0,
        **(selected_changes if selected_symbol == "SENSEX" else {}),
    )
    selected = nifty if selected_symbol == "NIFTY" else sensex

    entries = (
        TwoMarketDecisionEntryV1(
            child=nifty,
            eligible_for_comparison=True,
            rank_value=nifty.candidate.score,
            outcome_reason=(
                "SELECTED"
                if selected_symbol == "NIFTY"
                else "LOWER_RANK"
            ),
            rationale=(
                ("SELECTED_SCORE=80.000000",)
                if selected_symbol == "NIFTY"
                else ("LOWER_SCORE",)
            ),
        ),
        TwoMarketDecisionEntryV1(
            child=sensex,
            eligible_for_comparison=True,
            rank_value=sensex.candidate.score,
            outcome_reason=(
                "SELECTED"
                if selected_symbol == "SENSEX"
                else "LOWER_RANK"
            ),
            rationale=(
                ("SELECTED_SCORE=80.000000",)
                if selected_symbol == "SENSEX"
                else ("LOWER_SCORE",)
            ),
        ),
    )
    return TwoMarketDecisionResultV1(
        decision_result_id="decision-1",
        parent_cycle_id="parent-1",
        requested_at=selected.requested_at,
        completed_at=max(
            nifty.received_at,
            sensex.received_at,
        ),
        entries=entries,
        decision="SELECTED",
        selected_market=(
            selected.underlying_symbol,
            selected.exchange,
        ),
        selected_candidate_id=selected.candidate.candidate_id,
        timestamp_skew_seconds=0.0,
    )


def bridge(decision, *, result_id="bridge-1", age_seconds=180.0):
    return bridge_selected_market_to_planning(
        bridge_result_id=result_id,
        decision=decision,
        evaluated_at=decision.completed_at,
        maximum_candidate_age_seconds=age_seconds,
    )


@pytest.mark.parametrize(
    ("symbol", "direction", "expected_action"),
    (
        ("NIFTY", "BULLISH", "CALL"),
        ("NIFTY", "BEARISH", "PUT"),
        ("SENSEX", "BULLISH", "CALL"),
        ("SENSEX", "BEARISH", "PUT"),
    ),
)
def test_selected_market_produces_exact_traceable_planner_handoff(
    symbol,
    direction,
    expected_action,
):
    decision = selected_decision(
        selected_symbol=symbol,
        selected_changes={"direction": direction},
    )
    result = bridge(decision)
    selected_entry = next(
        item
        for item in decision.entries
        if item.outcome_reason == "SELECTED"
    )
    candidate = selected_entry.child.candidate

    assert type(result) is SelectedMarketPlanningBridgeResultV1
    assert result.parent_cycle_id == decision.parent_cycle_id
    assert result.parent_decision_id == decision.decision_result_id
    assert result.action == expected_action
    assert result.selected_child_action == expected_action
    assert result.planning_allowed is True
    assert result.selected_market == decision.selected_market
    assert result.selected_candidate is candidate
    assert result.selected_child_result_id == selected_entry.child.child_result_id
    assert result.candidate_id == candidate.candidate_id
    assert result.observation_id == candidate.observation_id
    assert result.direction == candidate.direction
    assert result.confidence == candidate.confidence
    assert result.score == candidate.score
    assert result.losing_market != result.selected_market
    assert result.losing_outcome_reason == "LOWER_RANK"
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.broker_order_submission is False


def test_no_trade_stays_no_trade_and_clears_selected_identity():
    base = selected_decision()
    entries = tuple(
        replace(
            entry,
            eligible_for_comparison=False,
            rank_value=0.0,
            outcome_reason="INELIGIBLE",
            rationale=("POLICY_BLOCKED",),
            child=replace(
                entry.child,
                terminal_status="FAILED",
                candidate=None,
                errors=("POLICY_BLOCKED",),
            ),
        )
        for entry in base.entries
    )
    decision = TwoMarketDecisionResultV1(
        decision_result_id="decision-no-trade",
        parent_cycle_id="parent-1",
        requested_at=base.requested_at,
        completed_at=base.completed_at,
        entries=entries,
        decision="NO_TRADE",
        selected_market=None,
        selected_candidate_id=None,
        timestamp_skew_seconds=0.0,
        blockers=("NO_ELIGIBLE_MARKET",),
    )
    result = bridge(decision, result_id="bridge-no-trade")

    assert result.parent_decision_id == "decision-no-trade"
    assert result.action == "NO_TRADE"
    assert result.selected_child_action == "NO_TRADE"
    assert result.planning_allowed is False
    assert result.selected_market is None
    assert result.selected_candidate is None
    assert result.selected_child_result_id is None
    assert result.candidate_id is None
    assert result.observation_id is None
    assert result.direction is None
    assert result.confidence is None
    assert result.score is None
    assert "NO_ELIGIBLE_MARKET" in result.blockers


def test_selected_candidate_that_becomes_stale_returns_traceable_wait():
    decision = selected_decision()
    result = bridge_selected_market_to_planning(
        bridge_result_id="bridge-stale",
        decision=decision,
        evaluated_at=(
            decision.completed_at + timedelta(seconds=181)
        ),
        maximum_candidate_age_seconds=180.0,
    )
    candidate = result.selected_candidate

    assert result.action == "WAIT"
    assert result.selected_child_action == "WAIT"
    assert result.planning_allowed is False
    assert candidate is not None
    assert result.candidate_id == candidate.candidate_id
    assert result.observation_id == candidate.observation_id
    assert result.direction == candidate.direction
    assert result.confidence == candidate.confidence
    assert result.score == candidate.score
    assert "SELECTED_CANDIDATE_STALE" in result.blockers


def test_future_candidate_timestamp_returns_wait():
    decision = selected_decision()
    selected = next(
        item
        for item in decision.entries
        if item.outcome_reason == "SELECTED"
    )
    object.__setattr__(
        selected.child.candidate,
        "market_timestamp",
        decision.completed_at + timedelta(seconds=1),
    )

    result = bridge(decision, result_id="bridge-future")

    assert result.action == "WAIT"
    assert result.planning_allowed is False
    assert "FUTURE_CANDIDATE_TIMESTAMP" in result.blockers


def test_losing_market_reason_and_rationale_are_preserved():
    decision = selected_decision(selected_symbol="SENSEX")
    result = bridge(decision, result_id="bridge-loser")

    assert result.selected_market == ("SENSEX", "BSE")
    assert result.losing_market == ("NIFTY", "NSE")
    assert result.losing_outcome_reason == "LOWER_RANK"
    assert result.losing_rationale == ("LOWER_SCORE",)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("candidate_id", "wrong-candidate"),
        ("observation_id", "wrong-observation"),
        ("direction", "BEARISH"),
        ("confidence", 1.0),
        ("score", 1.0),
    ),
)
def test_result_contract_rejects_selected_trace_mismatch(field, bad_value):
    result = bridge(selected_decision())

    with pytest.raises(ValueError):
        replace(result, **{field: bad_value})


def test_result_contract_rejects_wrong_selected_child_action():
    result = bridge(selected_decision())

    with pytest.raises(ValueError):
        replace(result, selected_child_action="PUT")


def test_result_contract_rejects_wait_without_blocker():
    result = bridge(selected_decision())

    with pytest.raises(ValueError):
        replace(
            result,
            action="WAIT",
            selected_child_action="WAIT",
            planning_allowed=False,
            blockers=(),
        )


def test_parent_contract_rejects_child_parent_cycle_mismatch():
    decision = selected_decision()
    selected = decision.entries[0]
    mismatched_child = replace(
        selected.child,
        parent_cycle_id="different-parent",
    )
    mismatched_entry = replace(selected, child=mismatched_child)

    with pytest.raises(ValueError, match="parent_cycle_id mismatch"):
        replace(
            decision,
            entries=(mismatched_entry, decision.entries[1]),
        )


def test_unavailable_child_cannot_become_selected():
    decision = selected_decision()
    selected = decision.entries[0]
    unavailable_child = replace(
        selected.child,
        terminal_status="UNAVAILABLE",
        candidate=None,
        blockers=("PROVIDER_UNAVAILABLE",),
    )

    with pytest.raises(ValueError):
        TwoMarketDecisionEntryV1(
            child=unavailable_child,
            eligible_for_comparison=True,
            rank_value=80.0,
            outcome_reason="SELECTED",
        )


def test_bridge_rejects_tampered_selected_observation_identity():
    decision = selected_decision()
    selected = decision.entries[0]
    object.__setattr__(
        selected.child,
        "observation_id",
        "tampered-observation",
    )

    with pytest.raises(ValueError, match="observation_id mismatch"):
        bridge(decision)


def test_bridge_has_no_contract_capital_provider_lifecycle_or_execution_dependencies():
    source = Path(
        "services/trade_planning/"
        "selected_market_planning_bridge.py"
    ).read_text(encoding="utf-8")
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = (
        "capital_quantity",
        "p6_planning_stage",
        "option_contract_selector",
        "provider",
        "broker",
        "dashboard",
        "paper_trading",
        "paper_portfolio",
        "persistence",
        "repository",
    )
    assert not any(
        any(token in module for token in forbidden)
        for module in imports
    )
    for token in (
        "place_order(",
        "submit_order(",
        "requests.",
        "random.",
        "datetime.now(",
        "datetime.utcnow(",
        "uuid4(",
        "time.sleep(",
    ):
        assert token not in source

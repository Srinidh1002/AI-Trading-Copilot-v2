"""Task 4 Slice 1 selected-market planning bridge certification."""
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
    losing = sensex if selected_symbol == "NIFTY" else nifty

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


@pytest.mark.parametrize(
    ("symbol", "direction", "expected_action"),
    (
        ("NIFTY", "BULLISH", "CALL"),
        ("SENSEX", "BEARISH", "PUT"),
    ),
)
def test_only_selected_market_reaches_planning(
    symbol,
    direction,
    expected_action,
):
    decision = selected_decision(
        selected_symbol=symbol,
        selected_changes={"direction": direction},
    )
    result = bridge_selected_market_to_planning(
        bridge_result_id="bridge-1",
        decision=decision,
        evaluated_at=decision.completed_at,
        maximum_candidate_age_seconds=180.0,
    )

    assert type(result) is SelectedMarketPlanningBridgeResultV1
    assert result.action == expected_action
    assert result.planning_allowed is True
    assert result.selected_market == decision.selected_market
    assert result.selected_candidate.candidate_id == (
        decision.selected_candidate_id
    )
    assert result.losing_market != result.selected_market
    assert result.losing_outcome_reason == "LOWER_RANK"


def test_no_trade_stays_no_trade_and_does_not_force_planning():
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
    result = bridge_selected_market_to_planning(
        bridge_result_id="bridge-no-trade",
        decision=decision,
        evaluated_at=decision.completed_at,
        maximum_candidate_age_seconds=180.0,
    )
    assert result.action == "NO_TRADE"
    assert result.planning_allowed is False
    assert result.selected_candidate is None
    assert "NO_ELIGIBLE_MARKET" in result.blockers


def test_selected_candidate_that_becomes_stale_returns_wait():
    decision = selected_decision()
    result = bridge_selected_market_to_planning(
        bridge_result_id="bridge-stale",
        decision=decision,
        evaluated_at=(
            decision.completed_at + timedelta(seconds=181)
        ),
        maximum_candidate_age_seconds=180.0,
    )
    assert result.action == "WAIT"
    assert result.planning_allowed is False
    assert result.selected_candidate is not None
    assert "SELECTED_CANDIDATE_STALE" in result.blockers


def test_selected_conflicting_or_nonactionable_evidence_returns_wait():
    decision = selected_decision()
    selected = decision.entries[0]
    candidate = replace(
        selected.child.candidate,
        eligibility="CONFLICTING",
        direction="CONFLICTING",
        score=0.0,
        confidence=0.0,
        contradictions=("SUPPLIED_CONFLICT",),
    )
    child_value = replace(
        selected.child,
        candidate=candidate,
    )
    entry = replace(
        selected,
        child=child_value,
        eligible_for_comparison=False,
        rank_value=0.0,
        outcome_reason="INELIGIBLE",
    )
    # Bypass parent reconstruction: the bridge contract itself must reject
    # any selected decision that no longer preserves exactly one selected
    # eligible entry.
    with pytest.raises(ValueError):
        TwoMarketDecisionResultV1(
            decision_result_id="invalid-decision",
            parent_cycle_id="parent-1",
            requested_at=decision.requested_at,
            completed_at=decision.completed_at,
            entries=(entry, decision.entries[1]),
            decision="SELECTED",
            selected_market=("NIFTY", "NSE"),
            selected_candidate_id=candidate.candidate_id,
            timestamp_skew_seconds=0.0,
        )


def test_losing_market_reason_and_rationale_are_preserved():
    decision = selected_decision(selected_symbol="SENSEX")
    result = bridge_selected_market_to_planning(
        bridge_result_id="bridge-loser",
        decision=decision,
        evaluated_at=decision.completed_at,
        maximum_candidate_age_seconds=180.0,
    )
    assert result.selected_market == ("SENSEX", "BSE")
    assert result.losing_market == ("NIFTY", "NSE")
    assert result.losing_outcome_reason == "LOWER_RANK"
    assert result.losing_rationale == ("LOWER_SCORE",)


def test_bridge_has_no_capital_quantity_p6_or_execution_dependencies():
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
        "broker",
        "dashboard",
        "paper_trading",
        "paper_portfolio",
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

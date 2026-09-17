"""Task 3 Slice 1 exact two-market contract certification."""
from dataclasses import replace
from datetime import timedelta
import ast
from pathlib import Path

import pytest

from services.contracts.two_market_child_terminal_result_v1 import (
    TwoMarketChildTerminalResultV1,
)
from services.contracts.two_market_decision_policy_v1 import (
    TwoMarketDecisionPolicyV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionEntryV1,
    TwoMarketDecisionResultV1,
)
from test_market_analysis_candidate_v1 import build


def child(symbol):
    value = build(underlying_symbol=symbol)
    return TwoMarketChildTerminalResultV1(
        child_result_id=f"child-{symbol}",
        parent_cycle_id="parent-1",
        observation_id=value.observation_id,
        underlying_symbol=value.underlying_symbol,
        exchange=value.exchange,
        requested_at=value.requested_at,
        received_at=value.received_at,
        terminal_status="COMPLETED",
        candidate=value,
    )


def test_policy_is_exact_two_market_and_paper_only():
    value = TwoMarketDecisionPolicyV1(30.0, 5.0)
    assert value.deterministic_market_order == (
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    )
    with pytest.raises(ValueError):
        replace(value, deterministic_market_order=(("NIFTY", "NSE"),))


def test_child_completed_and_failure_retention():
    nifty = child("NIFTY")
    assert nifty.candidate.underlying_symbol == "NIFTY"
    failed = TwoMarketChildTerminalResultV1(
        child_result_id="child-SENSEX",
        parent_cycle_id="parent-1",
        observation_id="obs-SENSEX",
        underlying_symbol="SENSEX",
        exchange="BSE",
        requested_at=nifty.requested_at,
        received_at=nifty.received_at,
        terminal_status="FAILED",
        errors=("PROVIDER_FAILURE",),
    )
    assert failed.candidate is None
    with pytest.raises(ValueError):
        replace(failed, errors=())


def test_parent_retains_exact_pair_and_one_selected_market():
    nifty = child("NIFTY")
    sensex = child("SENSEX")
    entries = (
        TwoMarketDecisionEntryV1(
            child=nifty,
            eligible_for_comparison=True,
            rank_value=nifty.candidate.score,
            outcome_reason="SELECTED",
            rationale=("HIGHER_SCORE",),
        ),
        TwoMarketDecisionEntryV1(
            child=sensex,
            eligible_for_comparison=True,
            rank_value=sensex.candidate.score,
            outcome_reason="LOWER_RANK",
            rationale=("LOWER_SCORE",),
        ),
    )
    result = TwoMarketDecisionResultV1(
        decision_result_id="decision-1",
        parent_cycle_id="parent-1",
        requested_at=nifty.requested_at,
        completed_at=max(nifty.received_at, sensex.received_at),
        entries=entries,
        decision="SELECTED",
        selected_market=("NIFTY", "NSE"),
        selected_candidate_id=nifty.candidate.candidate_id,
        timestamp_skew_seconds=0.0,
    )
    assert result.selected_market == ("NIFTY", "NSE")


def test_no_trade_retains_both_reasons():
    nifty = child("NIFTY")
    sensex = child("SENSEX")
    entries = (
        TwoMarketDecisionEntryV1(
            child=replace(
                nifty,
                terminal_status="FAILED",
                candidate=None,
                errors=("FAILURE",),
            ),
            eligible_for_comparison=False,
            rank_value=0.0,
            outcome_reason="CHILD_FAILED",
            rationale=("FAILURE",),
        ),
        TwoMarketDecisionEntryV1(
            child=replace(
                sensex,
                terminal_status="UNAVAILABLE",
                candidate=None,
                blockers=("STALE",),
            ),
            eligible_for_comparison=False,
            rank_value=0.0,
            outcome_reason="STALE",
            rationale=("STALE",),
        ),
    )
    result = TwoMarketDecisionResultV1(
        decision_result_id="decision-2",
        parent_cycle_id="parent-1",
        requested_at=nifty.requested_at,
        completed_at=nifty.received_at,
        entries=entries,
        decision="NO_TRADE",
        selected_market=None,
        selected_candidate_id=None,
        timestamp_skew_seconds=0.0,
        blockers=("NO_ELIGIBLE_MARKET",),
    )
    assert tuple(item.outcome_reason for item in result.entries) == (
        "CHILD_FAILED",
        "STALE",
    )


def test_contracts_do_not_import_four_market_or_runtime_layers():
    files = (
        "services/contracts/two_market_decision_policy_v1.py",
        "services/contracts/two_market_child_terminal_result_v1.py",
        "services/contracts/two_market_decision_result_v1.py",
    )
    forbidden = (
        "four_market",
        "market_ranking_engine",
        "broker",
        "dashboard",
        "paper_trading",
        "paper_portfolio",
    )
    for relative in files:
        source = Path(relative).read_text(encoding="utf-8")
        imports = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        assert not any(
            any(token in module for token in forbidden)
            for module in imports
        )

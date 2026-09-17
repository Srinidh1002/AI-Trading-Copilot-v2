"""Task 3 Slice 2 dedicated two-market ranker certification."""
from dataclasses import replace
from datetime import timedelta
import ast
from pathlib import Path

import pytest

from services.analysis.two_market_decision_ranker import (
    rank_two_market_candidates,
)
from services.contracts.two_market_child_terminal_result_v1 import (
    TwoMarketChildTerminalResultV1,
)
from services.contracts.two_market_decision_policy_v1 import (
    TwoMarketDecisionPolicyV1,
)
from test_market_analysis_candidate_v1 import build


def child(symbol, **candidate_changes):
    value = build(underlying_symbol=symbol)
    value = replace(value, **candidate_changes)
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


def decide(nifty, sensex, **policy_changes):
    policy = TwoMarketDecisionPolicyV1(180.0, 5.0)
    policy = replace(policy, **policy_changes)
    return rank_two_market_candidates(
        decision_result_id="decision-1",
        parent_cycle_id="parent-1",
        requested_at=min(nifty.requested_at, sensex.requested_at),
        completed_at=max(nifty.received_at, sensex.received_at),
        nifty=nifty,
        sensex=sensex,
        policy=policy,
    )


def test_higher_score_wins_and_loser_reason_is_retained():
    nifty = child("NIFTY", score=80.0, confidence=70.0)
    sensex = child("SENSEX", score=60.0, confidence=90.0)
    result = decide(nifty, sensex)
    assert result.selected_market == ("NIFTY", "NSE")
    assert result.entries[1].outcome_reason == "LOWER_RANK"
    assert "LOSER_SCORE=60.000000" in result.entries[1].rationale


def test_confidence_breaks_equal_score():
    nifty = child("NIFTY", score=75.0, confidence=65.0)
    sensex = child("SENSEX", score=75.0, confidence=85.0)
    result = decide(nifty, sensex)
    assert result.selected_market == ("SENSEX", "BSE")
    assert result.entries[0].outcome_reason == "LOWER_RANK"


def test_exact_tie_uses_deterministic_nifty_first_order():
    nifty = child("NIFTY", score=75.0, confidence=80.0)
    sensex = child("SENSEX", score=75.0, confidence=80.0)
    result = decide(nifty, sensex)
    assert result.selected_market == ("NIFTY", "NSE")
    assert result.entries[1].outcome_reason == "TIE_BREAK_LOSS"


def test_only_eligible_candidates_are_compared():
    nifty = child("NIFTY", score=40.0, confidence=40.0)
    sensex = child(
        "SENSEX",
        eligibility="INELIGIBLE",
        direction="NEUTRAL",
        score=0.0,
        confidence=0.0,
        blockers=("POLICY_BLOCKED",),
    )
    result = decide(nifty, sensex)
    assert result.selected_market == ("NIFTY", "NSE")
    assert result.entries[1].eligible_for_comparison is False
    assert result.entries[1].outcome_reason == "INELIGIBLE"


def test_one_child_failure_does_not_lose_other_result():
    nifty = child("NIFTY", score=55.0, confidence=55.0)
    original = child("SENSEX")
    sensex = replace(
        original,
        terminal_status="FAILED",
        candidate=None,
        errors=("CHILD_EXCEPTION",),
    )
    result = decide(nifty, sensex)
    assert result.selected_market == ("NIFTY", "NSE")
    assert result.entries[1].child.terminal_status == "FAILED"
    assert result.entries[1].outcome_reason == "CHILD_FAILED"


def test_neither_eligible_produces_no_trade():
    nifty = child(
        "NIFTY",
        eligibility="INELIGIBLE",
        direction="NEUTRAL",
        score=0.0,
        confidence=0.0,
        blockers=("NIFTY_BLOCKED",),
    )
    sensex = child(
        "SENSEX",
        eligibility="UNAVAILABLE",
        direction="UNAVAILABLE",
        score=0.0,
        confidence=0.0,
        blockers=("SENSEX_UNAVAILABLE",),
    )
    result = decide(nifty, sensex)
    assert result.decision == "NO_TRADE"
    assert result.selected_market is None
    assert "NO_ELIGIBLE_MARKET" in result.blockers


def test_stale_candidate_is_excluded():
    nifty = child("NIFTY", score=80.0)
    sensex = child("SENSEX", score=60.0)
    stale_candidate = replace(
        nifty.candidate,
        market_timestamp=nifty.candidate.market_timestamp - timedelta(seconds=240),
    )
    nifty = replace(nifty, candidate=stale_candidate)
    result = decide(nifty, sensex)
    assert result.selected_market == ("SENSEX", "BSE")
    assert result.entries[0].outcome_reason == "STALE"


def test_excessive_skew_blocks_pair_and_produces_no_trade():
    nifty = child("NIFTY", score=80.0)
    sensex = child("SENSEX", score=60.0)
    sensex_candidate = replace(
        sensex.candidate,
        market_timestamp=sensex.candidate.market_timestamp - timedelta(seconds=10),
    )
    sensex = replace(sensex, candidate=sensex_candidate)
    result = decide(nifty, sensex)
    assert result.decision == "NO_TRADE"
    assert tuple(item.outcome_reason for item in result.entries) == (
        "SKEW_BLOCKED",
        "SKEW_BLOCKED",
    )
    assert "CANDIDATE_TIMESTAMP_SKEW_EXCEEDED" in result.blockers


def test_ranker_has_no_four_market_runtime_or_execution_dependencies():
    source = Path(
        "services/analysis/two_market_decision_ranker.py"
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
        "broker",
        "dashboard",
        "paper_trading",
        "paper_portfolio",
        "trade_planning",
    )
    assert not any(
        any(token in module for token in forbidden)
        for module in imports
    )
    for token in ("place_order(", "submit_order(", "random."):
        assert token not in source

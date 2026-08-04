"""Task 3 Slice 4 certified two-market runtime integration tests."""
from __future__ import annotations

import ast
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from services.contracts.two_market_decision_policy_v1 import (
    TwoMarketDecisionPolicyV1,
)
from services.contracts.two_market_parent_cycle_input_v1 import (
    TwoMarketParentCycleInputV1,
)
from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
)
from services.paper_orchestration.certified_two_market_parent_runtime import (
    run_certified_two_market_parent_runtime,
)
from test_market_analysis_candidate_v1 import build
from test_two_market_runtime_readiness import (
    OfflineAnalysisPipeline,
    OfflineOptionPipeline,
    _cycle_input,
    _fixture,
)


def cycles():
    nifty = _cycle_input(_fixture("nifty_bullish_valid.json"))
    sensex = _cycle_input(_fixture("sensex_bullish_valid.json"))
    return nifty, sensex


def parent(nifty, sensex, **policy_changes):
    policy = TwoMarketDecisionPolicyV1(180.0, 5.0)
    policy = replace(policy, **policy_changes)
    return TwoMarketParentCycleInputV1(
        parent_cycle_id="certified-parent-1",
        decision_result_id="certified-decision-1",
        nifty_child_result_id="certified-child-NIFTY",
        sensex_child_result_id="certified-child-SENSEX",
        nifty_observation_id=nifty.observation_id,
        sensex_observation_id=sensex.observation_id,
        requested_at=nifty.cycle_requested_at,
        completed_at=max(nifty.received_at, sensex.received_at),
        decision_policy=policy,
    )


def readers(candidate_factory):
    return CertifiedLiveProviderReaders(
        quote_reader=lambda *args: pytest.fail("quote/network access forbidden"),
        analysis_pipeline=OfflineAnalysisPipeline(),
        option_decision_pipeline=OfflineOptionPipeline(),
        available_capital=10_000.0,
        candidate_reader=candidate_factory,
    )


def candidate_for(cycle, data, *, score, eligibility="ELIGIBLE"):
    direction = "BULLISH" if eligibility == "ELIGIBLE" else "NEUTRAL"
    value = build(underlying_symbol=cycle.underlying_symbol)
    return replace(
        value,
        observation_id=cycle.observation_id,
        symboltoken=data.symboltoken,
        requested_at=cycle.cycle_requested_at,
        market_timestamp=cycle.market_timestamp,
        received_at=cycle.received_at,
        score=score if eligibility == "ELIGIBLE" else 0.0,
        confidence=score if eligibility == "ELIGIBLE" else 0.0,
        eligibility=eligibility,
        direction=direction,
        blockers=() if eligibility == "ELIGIBLE" else ("POLICY_BLOCKED",),
    )


def test_runtime_evaluates_nifty_once_and_sensex_once_and_selects_one():
    nifty, sensex = cycles()
    calls = []
    parent_cycles = []

    def factory(cycle, data, analysis, captured, shared_context, *, parent_cycle_id):
        calls.append(cycle.underlying_symbol)
        parent_cycles.append(parent_cycle_id)
        return candidate_for(
            cycle,
            data,
            score=80.0 if cycle.underlying_symbol == "NIFTY" else 60.0,
        )

    result = run_certified_two_market_parent_runtime(
        parent(nifty, sensex),
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=readers(factory),
    )

    assert calls == ["NIFTY", "SENSEX"]
    assert parent_cycles == ["certified-parent-1", "certified-parent-1"]
    assert result.selected_market == ("NIFTY", "NSE")
    assert len(result.entries) == 2
    assert sum(e.outcome_reason == "SELECTED" for e in result.entries) == 1
    assert result.entries[1].outcome_reason == "LOWER_RANK"


def test_one_market_failure_keeps_other_terminal_result():
    nifty, sensex = cycles()
    calls = []

    def factory(cycle, data, analysis, captured, shared_context, *, parent_cycle_id):
        calls.append(cycle.underlying_symbol)
        if cycle.underlying_symbol == "NIFTY":
            raise RuntimeError("INJECTED_NIFTY_FAILURE")
        return candidate_for(cycle, data, score=70.0)

    result = run_certified_two_market_parent_runtime(
        parent(nifty, sensex),
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=readers(factory),
    )

    assert calls == ["NIFTY", "SENSEX"]
    assert result.entries[0].child.terminal_status == "FAILED"
    assert result.entries[1].child.terminal_status == "COMPLETED"
    assert result.selected_market == ("SENSEX", "BSE")


def test_neither_eligible_produces_no_trade_with_both_reasons():
    nifty, sensex = cycles()

    def factory(cycle, data, analysis, captured, shared_context, *, parent_cycle_id):
        return candidate_for(
            cycle,
            data,
            score=0.0,
            eligibility="INELIGIBLE",
        )

    result = run_certified_two_market_parent_runtime(
        parent(nifty, sensex),
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=readers(factory),
    )

    assert result.decision == "NO_TRADE"
    assert result.selected_market is None
    assert tuple(e.outcome_reason for e in result.entries) == (
        "INELIGIBLE",
        "INELIGIBLE",
    )


def test_runtime_applies_timestamp_skew_policy():
    nifty, sensex = cycles()
    shifted_timestamp = sensex.market_timestamp - timedelta(seconds=10)
    shifted_session = replace(
        sensex.session_validation,
        market_timestamp=shifted_timestamp,
    )
    sensex = replace(
        sensex,
        market_timestamp=shifted_timestamp,
        session_validation=shifted_session,
    )

    def factory(cycle, data, analysis, captured, shared_context, *, parent_cycle_id):
        return candidate_for(cycle, data, score=70.0)

    result = run_certified_two_market_parent_runtime(
        parent(nifty, sensex),
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=readers(factory),
    )

    assert result.decision == "NO_TRADE"
    assert tuple(e.outcome_reason for e in result.entries) == (
        "SKEW_BLOCKED",
        "SKEW_BLOCKED",
    )


def test_mismatched_child_cycle_is_rejected_before_evaluation():
    nifty, sensex = cycles()
    bad_sensex = replace(sensex, observation_id="wrong-observation")
    calls = []

    def factory(*args):
        calls.append(args)
        raise AssertionError("must not evaluate")

    with pytest.raises(ValueError, match="SENSEX certified child cycle mismatch"):
        run_certified_two_market_parent_runtime(
            parent(nifty, sensex),
            nifty_cycle=nifty,
            sensex_cycle=bad_sensex,
            readers=readers(factory),
        )
    assert calls == []


def test_runtime_bridge_has_no_four_market_planning_or_execution_dependencies():
    source = Path(
        "services/paper_orchestration/certified_two_market_parent_runtime.py"
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
        "datetime.now(",
        "datetime.utcnow(",
        "uuid4(",
        "random.",
        "time.sleep(",
    ):
        assert token not in source

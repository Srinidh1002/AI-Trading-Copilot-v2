"""Task 2B Slice 5: certified single-market candidate read seam."""
from __future__ import annotations

import ast
from dataclasses import replace

import pytest

from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
)
from services.paper_orchestration.certified_live_read_authorities import (
    CertifiedLiveAnalysisAuthority,
    CertifiedLiveDataAuthority,
    CertifiedLiveOpportunityAuthority,
    CertifiedSessionAuthority,
)
from test_market_analysis_candidate_v1 import (
    REQUESTED,
    build,
)
from test_two_market_runtime_readiness import (
    OfflineAnalysisPipeline,
    OfflineOptionPipeline,
    _cycle_input,
    _fixture,
)


@pytest.mark.parametrize(
    ("fixture_name", "symbol"),
    (
        ("nifty_bullish_valid.json", "NIFTY"),
        ("sensex_bullish_valid.json", "SENSEX"),
    ),
)
def test_each_existing_child_cycle_attaches_exactly_one_typed_candidate(
    fixture_name,
    symbol,
):
    replay = _fixture(fixture_name)
    cycle_input = _cycle_input(replay)
    expected = build(
        underlying_symbol=symbol,
        symboltoken=("99926000" if symbol == "NIFTY" else "99919000"),
    )
    expected = replace(
        expected,
        observation_id=cycle_input.observation_id,
        requested_at=cycle_input.cycle_requested_at,
        market_timestamp=cycle_input.market_timestamp,
        received_at=cycle_input.received_at,
    )
    calls = []

    def candidate_reader(cycle, data, supplied_analysis):
        calls.append((cycle, data, dict(supplied_analysis)))
        return expected

    readers = CertifiedLiveProviderReaders(
        quote_reader=lambda *args: pytest.fail("no quote/network access"),
        analysis_pipeline=OfflineAnalysisPipeline(),
        option_decision_pipeline=OfflineOptionPipeline(),
        available_capital=10_000.0,
        candidate_reader=candidate_reader,
    )

    data = CertifiedLiveDataAuthority(reader=readers.read_data)(cycle_input)
    session = CertifiedSessionAuthority()(cycle_input, data)
    analysis = CertifiedLiveAnalysisAuthority(reader=readers.read_analysis)(
        cycle_input,
        data,
        session,
    )
    opportunity = CertifiedLiveOpportunityAuthority(
        reader=readers.read_opportunity
    )(cycle_input, analysis, session)

    assert len(calls) == 1
    assert analysis.candidate is expected
    assert opportunity.evidence["market_analysis_candidate"] is expected
    assert expected.underlying_symbol == symbol
    assert expected.execution_mode == "PAPER"
    assert expected.live_execution_eligible is False
    assert expected.broker_order_submission is False


def test_existing_child_cycle_behavior_is_preserved_without_candidate_reader():
    replay = _fixture("nifty_bullish_valid.json")
    cycle_input = _cycle_input(replay)
    readers = CertifiedLiveProviderReaders(
        quote_reader=lambda *args: pytest.fail("no quote/network access"),
        analysis_pipeline=OfflineAnalysisPipeline(),
        option_decision_pipeline=OfflineOptionPipeline(),
        available_capital=10_000.0,
    )

    data = CertifiedLiveDataAuthority(reader=readers.read_data)(cycle_input)
    session = CertifiedSessionAuthority()(cycle_input, data)
    analysis = CertifiedLiveAnalysisAuthority(reader=readers.read_analysis)(
        cycle_input,
        data,
        session,
    )
    opportunity = CertifiedLiveOpportunityAuthority(
        reader=readers.read_opportunity
    )(cycle_input, analysis, session)

    assert analysis.candidate is None
    assert opportunity.opportunity_status == "NO_ACTION"
    assert opportunity.evidence["market_analysis_candidate"] is None


def test_candidate_reader_is_called_once_and_wrong_type_fails_closed():
    replay = _fixture("nifty_bullish_valid.json")
    cycle_input = _cycle_input(replay)
    readers = CertifiedLiveProviderReaders(
        quote_reader=lambda *args: pytest.fail("no quote/network access"),
        analysis_pipeline=OfflineAnalysisPipeline(),
        option_decision_pipeline=OfflineOptionPipeline(),
        available_capital=10_000.0,
        candidate_reader=lambda *_: {},
    )
    data = CertifiedLiveDataAuthority(reader=readers.read_data)(cycle_input)

    with pytest.raises(TypeError, match="MarketAnalysisCandidateV1"):
        readers.read_analysis(cycle_input, data)


def test_candidate_identity_mismatch_fails_closed():
    replay = _fixture("nifty_bullish_valid.json")
    cycle_input = _cycle_input(replay)
    wrong = build(underlying_symbol="SENSEX", symboltoken="99919000")
    readers = CertifiedLiveProviderReaders(
        quote_reader=lambda *args: pytest.fail("no quote/network access"),
        analysis_pipeline=OfflineAnalysisPipeline(),
        option_decision_pipeline=OfflineOptionPipeline(),
        available_capital=10_000.0,
        candidate_reader=lambda *_: wrong,
    )
    data = CertifiedLiveDataAuthority(reader=readers.read_data)(cycle_input)

    with pytest.raises(ValueError, match="candidate identity"):
        readers.read_analysis(cycle_input, data)


def test_candidate_seam_has_no_comparison_ranking_or_order_submission():
    for relative in (
        "services/paper_orchestration/certified_live_provider_readers.py",
        "services/paper_orchestration/certified_live_read_authorities.py",
    ):
        source = open(relative, encoding="utf-8").read()
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        forbidden = (
            "market_ranking",
            "opportunity_ranking",
            "paper_trade",
            "paper_portfolio",
            "dashboard",
            "broker",
        )
        assert not any(
            any(token in module for token in forbidden)
            for module in imports
        )
        for token in (
            "place_order(",
            "submit_order(",
            "compare_candidates(",
            "rank_candidates(",
        ):
            assert token not in source

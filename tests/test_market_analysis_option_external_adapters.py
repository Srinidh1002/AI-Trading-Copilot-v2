import ast
from dataclasses import replace
from pathlib import Path

import pytest

from services.analysis.market_analysis_option_external_adapters import (
    BroaderMarketEvidenceAdapterInputV1,
    ExternalContextEvidenceAdapterInputV1,
    OptionChainEvidenceAdapterInputV1,
    OptionContractRankingAdapterInputV1,
    adapt_broader_market_intelligence,
    adapt_external_market_context,
    adapt_option_chain_intelligence,
    adapt_option_contract_ranking,
    adapt_option_external_pillar_evidence,
)
from test_market_analysis_candidate_v1 import (
    REQUESTED,
    broader_market,
    external_context,
    identity,
    option_chain,
    option_contract_eligibility,
)


def chain_input(symbol="NIFTY", **changes):
    symbol, exchange, _ = identity(symbol)
    source = option_chain(symbol, exchange)
    values = {
        name: getattr(source, name)
        for name in source.__dataclass_fields__
        if name not in {"SCHEMA_VERSION", "EXECUTION_MODE", "LIVE_EXECUTION_ELIGIBLE", "execution_mode", "live_execution_eligible"}
    }
    values.update(changes)
    return OptionChainEvidenceAdapterInputV1(**values)


def ranking_input(symbol="NIFTY", **changes):
    symbol, exchange, _ = identity(symbol)
    source = option_contract_eligibility(symbol, exchange)
    values = {
        name: getattr(source, name)
        for name in source.__dataclass_fields__
        if name not in {"schema_version", "execution_mode", "live_execution_eligible"}
    }
    values.update(changes)
    return OptionContractRankingAdapterInputV1(**values)


def broader_input(symbol="NIFTY", **changes):
    symbol, exchange, _ = identity(symbol)
    source = broader_market(symbol, exchange)
    values = dict(
        broader_market_intelligence_result_id=source.broader_market_intelligence_result_id,
        created_at=source.created_at,
        underlying_symbol=symbol,
        exchange=exchange,
        cross_market_evidence=source.cross_market_evidence,
        breadth_evidence=source.breadth_evidence,
        volatility_context=source.volatility_context,
        intelligence_status=source.intelligence_status,
        aggregate_bias=source.aggregate_bias,
        aggregate_strength=source.aggregate_strength,
        confirmation_state=source.confirmation_state,
        divergence_state=source.divergence_state,
        supporting_evidence=source.supporting_evidence,
        contradictions=source.contradictions,
        blockers=source.blockers,
        warnings=source.warnings,
        source_timestamps=source.source_timestamps,
        metadata=source.metadata,
    )
    values.update(changes)
    return BroaderMarketEvidenceAdapterInputV1(**values)


def external_input(symbol="NIFTY", **changes):
    symbol, exchange, _ = identity(symbol)
    source = external_context(symbol, exchange)
    values = dict(
        external_market_context_result_id=source.external_market_context_result_id,
        created_at=source.created_at,
        underlying_symbol=symbol,
        exchange=exchange,
        global_context=source.global_context,
        institutional_context=source.institutional_context,
        event_context=source.event_context,
        context_status=source.context_status,
        aggregate_direction=source.aggregate_direction,
        aggregate_strength=source.aggregate_strength,
        confirmation_state=source.confirmation_state,
        risk_level=source.risk_level,
        entry_restriction_state=source.entry_restriction_state,
        analysis_allowed=source.analysis_allowed,
        new_entries_allowed=source.new_entries_allowed,
        available_component_count=source.available_component_count,
        unavailable_component_count=source.unavailable_component_count,
        confirming_component_count=source.confirming_component_count,
        conflicting_component_count=source.conflicting_component_count,
        supporting_evidence=source.supporting_evidence,
        contradictions=source.contradictions,
        blockers=source.blockers,
        warnings=source.warnings,
        source_timestamps=source.source_timestamps,
        metadata=source.metadata,
    )
    values.update(changes)
    return ExternalContextEvidenceAdapterInputV1(**values)


@pytest.mark.parametrize("symbol", ("NIFTY", "SENSEX"))
def test_valid_option_chain_preserves_identity_timestamp_metrics_and_ids(symbol):
    result = adapt_option_chain_intelligence(chain_input(symbol))
    assert (result.underlying_symbol, result.exchange) == identity(symbol)[:2]
    assert result.created_at == REQUESTED
    assert result.option_chain_snapshot_id == f"chain-{symbol}"
    assert result.metrics[0].metric_name == "PCR_OPEN_INTEREST"


def test_option_chain_ready_requires_real_metrics_and_rejects_duplicate_metrics():
    with pytest.raises(ValueError, match="requires metrics"):
        adapt_option_chain_intelligence(chain_input(metrics=(), bullish_metrics=(), valid_metric_count=0))
    metric = option_chain("NIFTY", "NSE").metrics[0]
    with pytest.raises(ValueError, match="duplicate option-chain metric"):
        chain_input(metrics=(metric, metric))


@pytest.mark.parametrize("symbol", ("NIFTY", "SENSEX"))
def test_valid_option_ranking_preserves_market_and_selected_contract(symbol):
    result = adapt_option_contract_ranking(ranking_input(symbol))
    assert result.ranking_status == "RANKED"
    assert result.selected_candidate.contract.underlying_symbol == symbol


def test_option_ranking_fails_closed_for_empty_ranked_result_and_identity_mismatch():
    with pytest.raises(ValueError, match="requires ranked candidates"):
        adapt_option_contract_ranking(ranking_input(ranked_candidates=()))
    sensex_candidate = option_contract_eligibility("SENSEX", "BSE").ranked_candidates[0]
    with pytest.raises(ValueError, match="identity mismatch"):
        ranking_input(ranked_candidates=(sensex_candidate,))


@pytest.mark.parametrize("symbol", ("NIFTY", "SENSEX"))
def test_valid_broader_market_preserves_supplied_cross_market_evidence(symbol):
    result = adapt_broader_market_intelligence(broader_input(symbol))
    assert result.intelligence_status == "READY"
    assert result.cross_market_evidence[0].primary_symbol == symbol
    assert result.available_component_count == 1


def test_broader_market_ready_requires_available_component_and_child_identity():
    with pytest.raises(ValueError, match="requires an available component"):
        adapt_broader_market_intelligence(broader_input(cross_market_evidence=()))
    foreign = broader_market("SENSEX", "BSE").cross_market_evidence[0]
    with pytest.raises(ValueError, match="identity mismatch"):
        broader_input(cross_market_evidence=(foreign,))


@pytest.mark.parametrize("symbol", ("NIFTY", "SENSEX"))
def test_valid_external_context_preserves_explicit_permissions(symbol):
    result = adapt_external_market_context(external_input(symbol))
    assert result.context_status == "READY"
    assert result.analysis_allowed is True
    assert result.new_entries_allowed is True


def test_external_context_nonready_states_fail_closed():
    with pytest.raises(ValueError, match="must fail closed"):
        adapt_external_market_context(external_input(context_status="BLOCKED", blockers=("BLOCKED",)))
    blocked = adapt_external_market_context(external_input(
        context_status="BLOCKED", aggregate_direction="UNAVAILABLE",
        aggregate_strength=0.0, confirmation_state="UNAVAILABLE",
        risk_level="UNAVAILABLE", entry_restriction_state="BLOCKED",
        analysis_allowed=False, new_entries_allowed=False,
        blockers=("BLOCKED",),
    ))
    assert blocked.analysis_allowed is False and blocked.new_entries_allowed is False


def test_option_external_pillar_retains_nested_provenance_immutably():
    provenance = {"nested": {"items": ["fixture"]}}
    result = adapt_option_external_pillar_evidence("READY", ("source-1",), provenance, {"value": [1]})
    provenance["nested"]["items"].append("changed")
    assert result.provenance["nested"]["items"] == ("fixture",)


def test_identical_supplied_inputs_are_deterministic():
    assert adapt_option_chain_intelligence(chain_input()) == adapt_option_chain_intelligence(chain_input())
    assert adapt_option_contract_ranking(ranking_input()) == adapt_option_contract_ranking(ranking_input())
    assert adapt_broader_market_intelligence(broader_input()) == adapt_broader_market_intelligence(broader_input())
    assert adapt_external_market_context(external_input()) == adapt_external_market_context(external_input())


def test_adapter_module_has_no_prohibited_imports_or_side_effects():
    path = Path(__file__).parents[1] / "services/analysis/market_analysis_option_external_adapters.py"
    text = path.read_text(encoding="utf-8")
    modules = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    forbidden = (
        "services.broker", "dashboard", "services.paper_orchestration",
        "services.paper_trading", "services.paper_portfolio",
        "services.opportunity_ranking", "services.market_ranking_engine",
        "services.analysis.option_chain", "services.options", "archive",
        "requests", "socket", "pathlib", "os", "uuid", "random",
    )
    assert not any(any(module == item or module.startswith(item + ".") for item in forbidden) for module in modules)
    for token in ("datetime.now(", "datetime.utcnow(", "uuid4(", "random.", "time.sleep(", "open(", "requests.", "place_order("):
        assert token not in text

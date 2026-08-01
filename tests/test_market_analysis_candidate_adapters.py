import ast
from dataclasses import replace
from pathlib import Path

import pytest

from services.analysis.market_analysis_candidate_adapters import (
    MultiTimeframeAdapterInputV1, RegimeEvidenceAdapterInputV1,
    TechnicalEvidenceAdapterInputV1, adapt_canonical_market_regime,
    adapt_multi_timeframe_snapshot, adapt_technical_intelligence,
    adapt_technical_pillar_evidence,
)
from test_market_analysis_candidate_v1 import (
    MARKET, REQUESTED, evidence, identity, regime, session, technical, timeframe,
)


def technical_input(symbol="NIFTY", **changes):
    symbol, exchange, _ = identity(symbol)
    source = technical(symbol, exchange)
    values = dict(technical_intelligence_result_id=f"adapted-technical-{symbol}", created_at=REQUESTED, multi_timeframe_snapshot_id=f"snapshot-{symbol}", multi_timeframe_quality_result_id=f"quality-{symbol}", underlying_symbol=symbol, exchange=exchange, timeframe_evidence=source.timeframe_evidence, status="READY", aggregate_bias="BULLISH", aggregate_strength=0.5)
    values.update(changes)
    return TechnicalEvidenceAdapterInputV1(**values)


def multi_input(symbol="NIFTY", **changes):
    symbol, exchange, _ = identity(symbol)
    values = dict(multi_timeframe_snapshot_id=f"adapted-snapshot-{symbol}", created_at=REQUESTED, underlying_symbol=symbol, exchange=exchange, required_timeframes=("5m",), timeframe_evidence=(timeframe(symbol, exchange),), primary_timeframe="5m", synchronization_reference_at=MARKET)
    values.update(changes)
    return MultiTimeframeAdapterInputV1(**values)


def regime_input(**changes):
    values = dict(market_regime_result_id="adapted-regime-NIFTY", created_at=REQUESTED, underlying_symbol="NIFTY", exchange="NSE", technical_context=technical("NIFTY", "NSE"), market_session_validation=session("NIFTY", "NSE"), broader_market_context=None, external_market_context=None, context_status="READY", directional_regime="BULLISH", trend_state="UPTREND", volatility_state="NORMAL", market_condition="NORMAL", confirmation_state="CONFIRMING", entry_suitability="SUITABLE", regime_strength=0.5, confidence=0.5, available_component_count=2, unavailable_component_count=2, confirming_component_count=1, conflicting_component_count=0, primary_regime="BULLISH", event_risk_state="NONE", entry_restriction_state="OPEN", analysis_allowed=True, new_entries_allowed=True)
    values.update(changes)
    return RegimeEvidenceAdapterInputV1(**values)


@pytest.mark.parametrize("symbol", ("NIFTY", "SENSEX"))
def test_valid_technical_adaptation_preserves_identity_timestamp_and_source_id(symbol):
    result = adapt_technical_intelligence(technical_input(symbol))
    assert (result.underlying_symbol, result.exchange) == identity(symbol)[:2]
    assert result.created_at == REQUESTED
    assert result.timeframe_evidence[0].timeframe_technical_evidence_id == f"technical-frame-{symbol}"


def test_ordered_multi_timeframe_adaptation_and_duplicate_empty_rejection():
    result = adapt_multi_timeframe_snapshot(multi_input())
    assert result.required_timeframes == ("5m",) and result.anchor_timeframe == "5m"
    duplicate = (timeframe("NIFTY", "NSE"), replace(timeframe("NIFTY", "NSE"), timeframe_evidence_id="duplicate"))
    with pytest.raises(ValueError, match="duplicate timeframe"):
        adapt_multi_timeframe_snapshot(multi_input(required_timeframes=("5m",), timeframe_evidence=duplicate))
    with pytest.raises(ValueError, match="timeframe evidence required"):
        adapt_multi_timeframe_snapshot(multi_input(timeframe_evidence=()))


def test_timeframe_identity_mismatch_and_stale_evidence_remain_fail_closed():
    with pytest.raises(ValueError, match="identity mismatch"):
        adapt_multi_timeframe_snapshot(multi_input(timeframe_evidence=(timeframe("SENSEX", "BSE"),)))
    stale = replace(timeframe("NIFTY", "NSE"), quality_status="STALE", blockers=("STALE",))
    result = adapt_multi_timeframe_snapshot(multi_input(timeframe_evidence=(stale,)))
    assert "TIMEFRAME_NOT_READY_5m" in result.blockers


def test_valid_missing_conflicting_and_blocked_regime_adaptation():
    assert adapt_canonical_market_regime(regime_input()).context_status == "READY"
    missing = adapt_canonical_market_regime(regime_input(technical_context=None))
    assert missing.context_status == "UNAVAILABLE" and "MANDATORY_REGIME_COMPONENT_UNAVAILABLE" in missing.blockers
    conflicting = adapt_canonical_market_regime(regime_input(contradictions=("SUPPLIED_CONFLICT",)))
    assert conflicting.context_status == "CONFLICTING" and conflicting.contradictions == ("SUPPLIED_CONFLICT",)
    blocked_session = replace(session("NIFTY", "NSE"), analysis_allowed=False, blockers=("SESSION_BLOCKED",))
    blocked = adapt_canonical_market_regime(regime_input(market_session_validation=blocked_session))
    assert blocked.context_status == "BLOCKED" and blocked.new_entries_allowed is False


def test_technical_pillar_statuses_preserve_sources_and_nested_immutability():
    source = {"nested": {"items": ["retained"]}}
    ready = adapt_technical_pillar_evidence("READY", ("pillar-source",), source, {"summary": [1]})
    unavailable = adapt_technical_pillar_evidence("UNAVAILABLE", (), {}, {})
    conflicting = adapt_technical_pillar_evidence("CONFLICTING", (), {}, {})
    source["nested"]["items"].append("changed")
    assert ready.provenance["nested"]["items"] == ("retained",)
    assert unavailable.status == "UNAVAILABLE" and conflicting.status == "CONFLICTING"


def test_identical_supplied_input_is_deterministic_and_technical_nonready_cannot_be_ready():
    assert adapt_technical_intelligence(technical_input()) == adapt_technical_intelligence(technical_input())
    blocked_frame = replace(technical("NIFTY", "NSE").timeframe_evidence[0], blockers=("INSUFFICIENT",))
    with pytest.raises(ValueError, match="explicit status"):
        adapt_technical_intelligence(technical_input(timeframe_evidence=(blocked_frame,)))



def test_required_timeframes_must_exactly_match_supplied_evidence_order():
    with pytest.raises(ValueError, match="requested timeframe order"):
        adapt_multi_timeframe_snapshot(
            multi_input(required_timeframes=("5m", "15m"))
        )


def test_regime_fails_closed_for_nonready_supplied_contexts():
    blocked_technical = replace(
        technical("NIFTY", "NSE"),
        status="FAILED",
        aggregate_bias="UNAVAILABLE",
        aggregate_strength=0.0,
        blockers=("TECHNICAL_FAILED",),
    )
    result = adapt_canonical_market_regime(
        regime_input(technical_context=blocked_technical)
    )
    assert result.context_status == "UNAVAILABLE"
    assert result.analysis_allowed is False
    assert result.new_entries_allowed is False
    assert "TECHNICAL_CONTEXT_UNAVAILABLE" in result.blockers


def test_adapter_inputs_reject_naive_timestamps_and_invalid_identity():
    with pytest.raises(ValueError):
        technical_input(created_at=REQUESTED.replace(tzinfo=None))
    with pytest.raises(ValueError, match="unsupported market identity"):
        multi_input(exchange="BSE")


def test_regime_mapping_inputs_are_defensively_frozen():
    source_timestamps = {"technical": REQUESTED}
    metadata = {"nested": {"values": [1]}}
    value = regime_input(
        source_timestamps=source_timestamps,
        metadata=metadata,
    )
    metadata["nested"]["values"].append(2)
    assert value.metadata["nested"]["values"] == (1,)

def test_adapter_module_has_no_prohibited_imports_or_side_effects():
    path = Path(__file__).parents[1] / "services/analysis/market_analysis_candidate_adapters.py"
    text = path.read_text(encoding="utf-8")
    modules = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import): modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module: modules.add(node.module)
    forbidden = ("services.broker", "dashboard", "services.paper_orchestration", "services.paper_trading", "services.paper_portfolio", "services.opportunity_ranking", "services.market_ranking_engine", "services.analysis.option_chain", "archive", "requests", "socket", "pathlib", "os", "uuid", "random")
    assert not any(any(module == item or module.startswith(item + ".") for item in forbidden) for module in modules)
    for token in ("datetime.now(", "datetime.utcnow(", "uuid4(", "random.", "time.sleep(", "open(", "requests.", "place_order("):
        assert token not in text

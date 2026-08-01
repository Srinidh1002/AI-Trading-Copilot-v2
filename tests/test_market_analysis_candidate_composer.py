import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from services.analysis.market_analysis_candidate_composer import (
    MarketAnalysisCandidateCompositionInputV1,
    MarketAnalysisCandidateCompositionPolicyV1,
    compose_market_analysis_candidate,
)
from test_market_analysis_candidate_v1 import (
    MARKET,
    NAMES,
    RECEIVED,
    REQUESTED,
    evidence,
    identity,
    nonready_broader_market,
    nonready_canonical_input,
    nonready_external_context,
    valid_canonical_inputs,
)


def composition(symbol="NIFTY", **changes):
    symbol, exchange, option_exchange = identity(symbol)
    values = dict(
        candidate_id=f"candidate-{symbol}",
        observation_id=f"observation-{symbol}",
        underlying_symbol=symbol,
        exchange=exchange,
        option_exchange=option_exchange,
        symboltoken=f"token-{symbol}",
        requested_at=REQUESTED,
        market_timestamp=MARKET,
        received_at=RECEIVED,
        broader_market=None,
        external_context=None,
        evidence_references={
            "technical": {"id": f"technical-{symbol}"}
        },
        provenance={"fixture": {"symbol": symbol}},
    )
    values.update(valid_canonical_inputs(symbol))
    values.update({name: evidence() for name in NAMES})
    values.update(changes)
    return MarketAnalysisCandidateCompositionInputV1(**values)


def policy(
    direction="BULLISH",
    eligibility="ELIGIBLE",
    confidence=75.0,
    score=75.0,
    **changes,
):
    values = dict(
        direction=direction,
        eligibility=eligibility,
        confidence=confidence,
        score=score,
    )
    values.update(changes)
    return MarketAnalysisCandidateCompositionPolicyV1(**values)


@pytest.mark.parametrize("symbol", ("NIFTY", "SENSEX"))
def test_deterministic_valid_candidate_preserves_exact_market_identity(symbol):
    result = compose_market_analysis_candidate(composition(symbol), policy())
    assert (
        result.underlying_symbol,
        result.exchange,
        result.option_exchange,
    ) == identity(symbol)
    assert result == compose_market_analysis_candidate(
        composition(symbol), policy()
    )


def test_composition_input_is_deeply_immutable():
    references = {"technical": {"ids": ["technical-NIFTY"]}}
    provenance = {"source": {"values": ["fixture"]}}
    value = composition(
        evidence_references=references,
        provenance=provenance,
    )
    references["technical"]["ids"].append("changed")
    provenance["source"]["values"].append("changed")
    assert value.evidence_references["technical"]["ids"] == (
        "technical-NIFTY",
    )
    assert value.provenance["source"]["values"] == ("fixture",)
    with pytest.raises(FrozenInstanceError):
        value.symboltoken = "changed"


def test_input_rejects_invalid_identity_and_timestamp_order():
    with pytest.raises(ValueError, match="unsupported market identity"):
        composition(exchange="BSE")
    with pytest.raises(ValueError, match="timestamp ordering"):
        composition(market_timestamp=RECEIVED)


def test_input_rejects_nested_identity_mismatch():
    values = valid_canonical_inputs("SENSEX")
    with pytest.raises(ValueError, match="identity mismatch"):
        composition(freshness=values["freshness"])


def test_missing_or_stale_required_evidence_fails_closed_explicitly():
    missing = compose_market_analysis_candidate(
        composition(freshness=None), policy()
    )
    stale = compose_market_analysis_candidate(
        composition(freshness=nonready_canonical_input("freshness")),
        policy(),
    )
    assert (
        missing.eligibility,
        missing.direction,
        missing.confidence,
        missing.score,
    ) == ("UNAVAILABLE", "UNAVAILABLE", 0.0, 0.0)
    assert stale.eligibility == "UNAVAILABLE"
    assert "EVIDENCE_UNAVAILABLE_FRESHNESS" in missing.blockers


@pytest.mark.parametrize(
    "field_name,context",
    (
        (
            "broader_market",
            nonready_broader_market("NIFTY", "NSE"),
        ),
        (
            "external_context",
            nonready_external_context("NIFTY", "NSE"),
        ),
    ),
)
def test_unavailable_optional_context_fails_closed_explicitly(
    field_name,
    context,
):
    result = compose_market_analysis_candidate(
        composition(**{field_name: context}), policy()
    )
    assert result.eligibility == "UNAVAILABLE"
    assert f"EVIDENCE_UNAVAILABLE_{field_name.upper()}" in result.blockers


def test_explicit_contradiction_wins_without_neutral_fallback():
    result = compose_market_analysis_candidate(
        composition(),
        policy(contradictions=("TECHNICAL_OPTION_CONFLICT",)),
    )
    assert (
        result.direction,
        result.eligibility,
        result.confidence,
        result.score,
    ) == ("CONFLICTING", "CONFLICTING", 0.0, 0.0)
    assert result.contradictions == ("TECHNICAL_OPTION_CONFLICT",)


@pytest.mark.parametrize("direction", ("BULLISH", "BEARISH"))
def test_directional_policy_outputs(direction):
    result = compose_market_analysis_candidate(
        composition(), policy(direction)
    )
    assert result.direction == direction
    assert result.eligibility == "ELIGIBLE"


def test_neutral_policy_becomes_explicit_no_trade_not_forced_trade():
    result = compose_market_analysis_candidate(
        composition(), policy("NEUTRAL")
    )
    assert result.eligibility == "INELIGIBLE"
    assert result.confidence == result.score == 0.0
    assert "DIRECTION_NEUTRAL_NO_TRADE" in result.blockers


def test_explicit_policy_blocker_forces_ineligible_zeroed_output():
    result = compose_market_analysis_candidate(
        composition(),
        policy(blockers=("MANUAL_ANALYTICAL_BLOCK",)),
    )
    assert result.eligibility == "INELIGIBLE"
    assert result.confidence == result.score == 0.0
    assert result.blockers == ("MANUAL_ANALYTICAL_BLOCK",)


@pytest.mark.parametrize(
    "eligibility",
    ("INELIGIBLE", "UNAVAILABLE", "CONFLICTING"),
)
def test_noneligible_policy_without_diagnostic_is_fail_closed(eligibility):
    result = compose_market_analysis_candidate(
        composition(),
        policy(
            eligibility=eligibility,
            direction=(
                "CONFLICTING"
                if eligibility == "CONFLICTING"
                else "BULLISH"
            ),
        ),
    )
    if eligibility == "CONFLICTING":
        assert result.eligibility == "INELIGIBLE"
    else:
        assert result.eligibility == "INELIGIBLE"
    assert result.confidence == result.score == 0.0
    assert "POLICY_INELIGIBLE" in result.blockers


@pytest.mark.parametrize(
    "changes",
    (
        {"direction": ""},
        {"direction": "CALL"},
        {"eligibility": "TRADE"},
        {"confidence": -0.1},
        {"confidence": 100.1},
        {"score": -0.1},
        {"score": 100.1},
    ),
)
def test_policy_rejects_invalid_values(changes):
    with pytest.raises((TypeError, ValueError)):
        policy(**changes)


def test_evidence_and_provenance_are_retained_without_mutation():
    references = {"technical": {"ids": ["technical-NIFTY"]}}
    provenance = {"source": {"values": ["fixture"]}}
    result = compose_market_analysis_candidate(
        composition(
            evidence_references=references,
            provenance=provenance,
        ),
        policy(),
    )
    references["technical"]["ids"].append("changed")
    provenance["source"]["values"].append("changed")
    assert result.evidence_references["technical"]["ids"] == (
        "technical-NIFTY",
    )
    assert result.provenance["source"]["values"] == ("fixture",)


def test_composer_has_no_prohibited_dependencies_or_side_effect_primitives():
    path = (
        Path(__file__).parents[1]
        / "services/analysis/market_analysis_candidate_composer.py"
    )
    text = path.read_text(encoding="utf-8")
    modules = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    forbidden = (
        "services.broker",
        "dashboard",
        "services.paper_orchestration",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.opportunity_ranking",
        "services.market_ranking_engine",
        "services.analysis.option_chain",
        "archive",
        "requests",
        "socket",
        "pathlib",
        "os",
        "random",
        "uuid",
    )
    assert not any(
        any(
            module == item or module.startswith(item + ".")
            for item in forbidden
        )
        for module in modules
    )
    for token in (
        "datetime.now(",
        "datetime.utcnow(",
        "uuid4(",
        "random.",
        "time.sleep(",
        "open(",
        "requests.",
        "place_order(",
    ):
        assert token not in text

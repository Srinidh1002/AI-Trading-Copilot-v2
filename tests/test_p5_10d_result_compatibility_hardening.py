"""Focused compatibility hardening coverage for the canonical regime result."""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.contracts.broader_market_regime_component_result_v1 import BroaderMarketRegimeComponentResultV1
from services.contracts.canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
from services.contracts.external_context_regime_component_result_v1 import ExternalContextRegimeComponentResultV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.technical_regime_component_result_v1 import TechnicalRegimeComponentResultV1


TS = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
PRIMARY = (
    "STRONG_BULLISH", "BULLISH", "RANGE_BOUND", "BEARISH", "STRONG_BEARISH",
    "HIGH_VOLATILITY", "EVENT_RISK", "CONFLICTING", "UNAVAILABLE", "BLOCKED",
)


def make_result(primary: str = "BULLISH", identity: tuple[str, str] = ("NIFTY", "NSE"), **changes):
    symbol, exchange = identity
    values = {
        "market_regime_result_id": "result-1",
        "created_at": TS,
        "underlying_symbol": symbol,
        "exchange": exchange,
        "technical_context": None,
        "broader_market_context": None,
        "external_market_context": None,
        "market_session_validation": None,
        "context_status": "READY",
        "directional_regime": "BULLISH",
        "trend_state": "UPTREND",
        "volatility_state": "NORMAL",
        "market_condition": "NORMAL",
        "confirmation_state": "CONFIRMING",
        "entry_suitability": "SUITABLE",
        "regime_strength": 0.6,
        "confidence": 0.7,
        "available_component_count": 4,
        "unavailable_component_count": 0,
        "confirming_component_count": 2,
        "conflicting_component_count": 0,
        "primary_regime": primary,
        "breadth_state": "POSITIVE",
        "event_risk_state": "NONE",
        "entry_restriction_state": "OPEN",
        "analysis_allowed": True,
        "new_entries_allowed": True,
    }
    if primary == "HIGH_VOLATILITY":
        values.update(volatility_state="HIGH", market_condition="HIGH_VOLATILITY")
    elif primary == "EVENT_RISK":
        values.update(event_risk_state="HIGH", entry_restriction_state="WARNING", entry_suitability="CAUTION", market_condition="EVENT_RISK")
    elif primary == "CONFLICTING":
        values.update(context_status="CONFLICTING", directional_regime="CONFLICTING", trend_state="CONFLICTING", confirmation_state="CONFLICTING", contradictions=("COMPONENT_CONFLICT",))
    elif primary == "UNAVAILABLE":
        values.update(
            context_status="UNAVAILABLE", directional_regime="UNAVAILABLE", trend_state="UNAVAILABLE",
            volatility_state="UNAVAILABLE", market_condition="UNAVAILABLE", confirmation_state="UNAVAILABLE",
            entry_suitability="UNAVAILABLE", regime_strength=0.0, confidence=0.0,
            available_component_count=0, unavailable_component_count=4, confirming_component_count=0,
            breadth_state="UNAVAILABLE", event_risk_state="UNAVAILABLE", entry_restriction_state="UNAVAILABLE",
            analysis_allowed=False, new_entries_allowed=False,
        )
    elif primary == "BLOCKED":
        values.update(
            context_status="BLOCKED", directional_regime="BLOCKED", entry_suitability="BLOCKED",
            entry_restriction_state="BLOCKED", blockers=("SESSION_BLOCK",), analysis_allowed=False,
            new_entries_allowed=False,
        )
    values.update(changes)
    return CanonicalMarketRegimeResultV1(**values)


def technical_component(identity=("NIFTY", "NSE")):
    return TechnicalRegimeComponentResultV1(
        "technical-1", TS, identity[0], identity[1], None, "UNAVAILABLE", "UNAVAILABLE",
        "UNAVAILABLE", "UNAVAILABLE", 0.0, 0.0, "UNAVAILABLE", 0, 0,
    )


def broader_component(identity=("NIFTY", "NSE")):
    return BroaderMarketRegimeComponentResultV1(
        "broader-1", TS, identity[0], identity[1], None, "UNAVAILABLE", "UNAVAILABLE",
        "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", 0.0, 0.0, "UNAVAILABLE", 0, 0,
    )


def external_component(identity=("NIFTY", "NSE")):
    return ExternalContextRegimeComponentResultV1(
        "external-1", TS, identity[0], identity[1], None, "UNAVAILABLE", "UNAVAILABLE",
        "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", 0.0, 0.0, "UNAVAILABLE",
    )


def session_component(identity=("NIFTY", "NSE")):
    return MarketSessionValidationV1(
        validation_id="session-1", evaluated_at=TS, market_timestamp=TS, symbol=identity[0],
        exchange=identity[1], timezone="UTC", trading_date=TS.date(), session_state="CLOSED",
        session_phase="CLOSED_ALL_DAY", trading_day_status="TRADING_DAY",
    )


@pytest.mark.parametrize("primary", PRIMARY)
def test_all_primary_regimes_construct_when_their_coherence_requirements_hold(primary):
    assert make_result(primary).primary_regime == primary


def test_component_references_accept_exact_types_and_partial_or_absent_children():
    policy_result = make_result(
        technical_regime_component=technical_component(),
        broader_market_regime_component=broader_component(),
        external_context_regime_component=external_component(),
        market_session_validation=session_component(),
    )
    assert policy_result.technical_regime_component is not None
    assert make_result("UNAVAILABLE").technical_regime_component is None
    assert make_result("BLOCKED").market_session_validation is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("technical_regime_component", object()),
        ("technical_regime_component", {}),
        ("technical_regime_component", broader_component()),
        ("broader_market_regime_component", object()),
        ("broader_market_regime_component", {}),
        ("broader_market_regime_component", technical_component()),
        ("external_context_regime_component", object()),
        ("external_context_regime_component", {}),
        ("external_context_regime_component", technical_component()),
        ("market_session_validation", object()),
        ("market_session_validation", {}),
        ("market_session_validation", technical_component()),
    ],
)
def test_component_references_reject_wrong_types(field, value):
    with pytest.raises(TypeError):
        make_result(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("technical_regime_component", technical_component(("SENSEX", "BSE"))),
        ("broader_market_regime_component", broader_component(("SENSEX", "BSE"))),
        ("external_context_regime_component", external_component(("SENSEX", "BSE"))),
        ("market_session_validation", session_component(("SENSEX", "BSE"))),
    ],
)
def test_component_references_reject_identity_mismatches(field, value):
    with pytest.raises(ValueError):
        make_result(**{field: value})


@pytest.mark.parametrize(
    "field,valid_value,invalid_value",
    [
        ("trend_state", "SIDEWAYS", "INVALID"),
        ("volatility_state", "EXTREME", "INVALID"),
        ("breadth_state", "MIXED", "INVALID"),
        ("confirmation_state", "PARTIAL", "INVALID"),
        ("entry_suitability", "CAUTION", "INVALID"),
        ("event_risk_state", "MODERATE", "INVALID"),
        ("entry_restriction_state", "SESSION_OWNED", "INVALID"),
    ],
)
def test_dimension_vocabularies_are_controlled(field, valid_value, invalid_value):
    changes = {field: valid_value}
    if field == "entry_restriction_state":
        changes["new_entries_allowed"] = False
        changes["entry_suitability"] = "CAUTION"
    assert getattr(make_result(**changes), field) == valid_value
    with pytest.raises(ValueError):
        make_result(**{field: invalid_value})


@pytest.mark.parametrize("field", ("primary_regime", "context_status"))
def test_primary_regime_and_context_status_reject_unknown_values(field):
    with pytest.raises(ValueError):
        make_result(**{field: "INVALID"})


@pytest.mark.parametrize("field", ("regime_strength", "confidence"))
@pytest.mark.parametrize("invalid_value", (-0.1, 1.1, True, False, float("nan"), float("inf"), float("-inf")))
def test_strength_and_confidence_are_finite_unit_interval_numbers(field, invalid_value):
    with pytest.raises(ValueError):
        make_result(**{field: invalid_value})


def test_required_status_and_primary_coherence_rules_are_enforced():
    with pytest.raises(ValueError):
        make_result("BLOCKED", blockers=())
    with pytest.raises(ValueError):
        make_result("BLOCKED", new_entries_allowed=True, analysis_allowed=True)
    with pytest.raises(ValueError):
        make_result("CONFLICTING", contradictions=())
    with pytest.raises(ValueError):
        make_result("UNAVAILABLE", regime_strength=0.1)
    with pytest.raises(ValueError):
        make_result(warnings=("WARN",))
    with pytest.raises(ValueError):
        make_result(blockers=("BLOCK",))
    with pytest.raises(ValueError):
        make_result(contradictions=("CONFLICT",))
    with pytest.raises(ValueError):
        make_result(context_status="READY_WITH_WARNINGS", warnings=())
    with pytest.raises(ValueError):
        make_result(analysis_allowed=False, new_entries_allowed=True)
    with pytest.raises(ValueError):
        make_result("HIGH_VOLATILITY", volatility_state="NORMAL")
    with pytest.raises(ValueError):
        make_result("EVENT_RISK", event_risk_state="LOW")
    with pytest.raises(ValueError):
        make_result(entry_restriction_state="BLOCKED", new_entries_allowed=True, analysis_allowed=True)


@pytest.mark.parametrize("identity", (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE")))
def test_supported_market_identities_are_accepted(identity):
    assert make_result(identity=identity).underlying_symbol == identity[0]


@pytest.mark.parametrize("identity", (("NIFTY", "BSE"), ("SENSEX", "NSE"), ("UNKNOWN", "NSE")))
def test_cross_exchange_and_unsupported_identities_are_rejected(identity):
    with pytest.raises(ValueError):
        make_result(identity=identity)


def test_serialization_immutability_and_execution_restrictions_are_deterministic():
    timestamps = {"z-source": TS, "a-source": TS}
    metadata = {"nested": {"value": 1}}
    result = make_result(
        technical_regime_component=technical_component(), source_timestamps=timestamps, metadata=metadata,
    )

    first_dict = result.to_dict()
    first_json = result.to_json()
    first_semantic = result.semantic_dict()
    assert first_dict == result.to_dict()
    assert first_json == result.to_json()
    assert first_semantic == result.semantic_dict()
    assert json.loads(first_json)["technical_regime_component"] is not None
    assert first_dict["broader_market_regime_component"] is None
    assert tuple(result.source_timestamps) == ("A-SOURCE", "Z-SOURCE")
    with pytest.raises(TypeError):
        result.source_timestamps["NEW"] = TS
    with pytest.raises(TypeError):
        result.metadata["new"] = "value"
    with pytest.raises(TypeError):
        result.metadata["nested"]["value"] = 2
    with pytest.raises(FrozenInstanceError):
        result.primary_regime = "BEARISH"
    timestamps["z-source"] = datetime(2027, 1, 1, tzinfo=timezone.utc)
    metadata["nested"]["value"] = 2
    assert result.to_dict() == first_dict
    assert "market_regime_result_id" not in first_semantic
    assert "created_at" not in first_semantic
    with pytest.raises(ValueError):
        make_result(execution_mode="LIVE")
    with pytest.raises(ValueError):
        make_result(live_execution_eligible=True)


def test_isolated_import_has_no_runtime_or_provider_side_effects():
    root = Path(__file__).resolve().parents[1]
    command = (
        "import sys; import services.contracts; "
        "from services.contracts.canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1; "
        "blocked=('pandas','numpy','scipy','requests','yfinance','SmartApi','smartapi','streamlit'); "
        "print(any(name in sys.modules for name in blocked))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", command], cwd=root, check=True, capture_output=True, text=True,
    )
    assert completed.stdout.strip() == "False"

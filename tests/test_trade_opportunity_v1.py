import json
from datetime import date, datetime, timezone

import pytest

from services.contracts.trade_opportunity_v1 import (
    TradeOpportunityV1,
)


NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)
EXPIRY = date(2026, 7, 30)


def make_opportunity(**changes):
    values = dict(
        opportunity_id="o1",
        created_at=NOW,
        snapshot_id="s1",
        decision_id="d1",
        technical_intelligence_result_id="t1",
        option_chain_intelligence_result_id="i1",
        option_contract_ranking_id="r1",
        session_validation_id="v1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        expiry=EXPIRY,
        action="BUY",
        directional_bias="BULLISH",
        option_type="CALL",
        contract_id="c1",
        trading_symbol="NIFTY-CALL",
        instrument_token=None,
        strike=25000,
        lot_size=25,
        reference_option_price=100,
        technical_strength=0.8,
        option_chain_strength=0.7,
        contract_ranking_score=0.9,
        decision_confidence=0.75,
        opportunity_score=0.79,
        opportunity_status="READY",
        supporting_evidence=("aligned evidence",),
    )
    values.update(changes)
    return TradeOpportunityV1(**values)


def test_valid_ready_opportunity():
    result = make_opportunity()

    assert result.opportunity_ready is True
    assert result.schema_version == "trade_opportunity.v1"
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.contract_id == "c1"


def test_valid_ready_with_warnings():
    result = make_opportunity(
        opportunity_status="READY_WITH_WARNINGS",
        warnings=("partial evidence",),
    )

    assert result.opportunity_ready is True
    assert result.warnings == ("PARTIAL EVIDENCE",)


def test_valid_sell_put_opportunity():
    result = make_opportunity(
        action="SELL",
        directional_bias="BEARISH",
        option_type="PUT",
    )

    assert result.action == "SELL"
    assert result.option_type == "PUT"


@pytest.mark.parametrize(
    "status",
    [
        "BLOCKED",
        "INSUFFICIENT_DATA",
        "CONFLICTING",
        "FAILED",
    ],
)
def test_blocking_statuses_require_blockers(status):
    result = make_opportunity(
        opportunity_status=status,
        blockers=("blocked",),
        contract_id=None,
        trading_symbol=None,
        strike=None,
        lot_size=None,
        expiry=None,
        option_type=None,
        action="WAIT",
        directional_bias="NEUTRAL",
        technical_strength=0,
        option_chain_strength=0,
        contract_ranking_score=0,
        decision_confidence=0,
        opportunity_score=0,
    )

    assert result.opportunity_ready is False
    assert result.blockers == ("BLOCKED",)


@pytest.mark.parametrize(
    "status",
    [
        "BLOCKED",
        "INSUFFICIENT_DATA",
        "CONFLICTING",
        "FAILED",
    ],
)
def test_blocking_status_without_blockers_rejected(status):
    with pytest.raises(ValueError):
        make_opportunity(
            opportunity_status=status,
            blockers=(),
            contract_id=None,
            trading_symbol=None,
            strike=None,
            lot_size=None,
            expiry=None,
            option_type=None,
            action="WAIT",
            directional_bias="NEUTRAL",
        )


@pytest.mark.parametrize(
    "action",
    ["WAIT", "HOLD"],
)
def test_no_action_status(action):
    result = make_opportunity(
        opportunity_status="NO_ACTION",
        action=action,
        directional_bias="NEUTRAL",
        option_type=None,
        expiry=None,
        contract_id=None,
        trading_symbol=None,
        strike=None,
        lot_size=None,
        reference_option_price=None,
        technical_strength=0,
        option_chain_strength=0,
        contract_ranking_score=0,
        decision_confidence=0,
        opportunity_score=0,
        supporting_evidence=(),
    )

    assert result.opportunity_ready is False
    assert result.action == action


def test_no_action_rejects_directional_action():
    with pytest.raises(ValueError):
        make_opportunity(
            opportunity_status="NO_ACTION",
        )


def test_ready_requires_complete_contract_identity():
    for field in (
        "expiry",
        "contract_id",
        "trading_symbol",
        "strike",
        "lot_size",
    ):
        with pytest.raises(ValueError):
            make_opportunity(**{field: None})


def test_non_ready_rejects_partial_contract_identity():
    with pytest.raises(ValueError):
        make_opportunity(
            opportunity_status="BLOCKED",
            blockers=("blocked",),
            contract_id=None,
        )


def test_action_bias_must_match():
    with pytest.raises(ValueError):
        make_opportunity(
            directional_bias="BEARISH",
        )


def test_action_option_type_must_match():
    with pytest.raises(ValueError):
        make_opportunity(
            option_type="PUT",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("technical_strength", -0.1),
        ("technical_strength", 1.1),
        ("option_chain_strength", float("nan")),
        ("contract_ranking_score", -1),
        ("decision_confidence", 2),
        ("opportunity_score", -0.1),
        ("opportunity_score", 1.1),
        ("strike", 0),
        ("lot_size", 0),
        ("reference_option_price", 0),
    ],
)
def test_invalid_numeric_values(field, value):
    with pytest.raises((TypeError, ValueError)):
        make_opportunity(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("opportunity_id", ""),
        ("snapshot_id", ""),
        ("decision_id", ""),
        ("technical_intelligence_result_id", ""),
        ("option_chain_intelligence_result_id", ""),
        ("option_contract_ranking_id", ""),
        ("session_validation_id", ""),
        ("created_at", datetime(2026, 7, 27)),
        ("underlying_symbol", "NIFTY50"),
        ("exchange", "BSE"),
        ("action", "LONG"),
        ("directional_bias", "UP"),
        ("option_type", "CE"),
        ("opportunity_status", "UNKNOWN"),
    ],
)
def test_invalid_top_level_values(field, value):
    with pytest.raises((TypeError, ValueError)):
        make_opportunity(**{field: value})


def test_ready_cannot_have_blockers():
    with pytest.raises(ValueError):
        make_opportunity(
            blockers=("blocked",),
        )


def test_ready_cannot_have_warnings():
    with pytest.raises(ValueError):
        make_opportunity(
            warnings=("warning",),
        )


def test_ready_with_warnings_requires_warning():
    with pytest.raises(ValueError):
        make_opportunity(
            opportunity_status="READY_WITH_WARNINGS",
        )


def test_duplicate_text_values_are_rejected():
    with pytest.raises(ValueError):
        make_opportunity(
            supporting_evidence=("aligned", "ALIGNED"),
        )


def test_serialization_and_semantic_output():
    result = make_opportunity()
    payload = result.to_dict()

    assert payload["expiry"] == "2026-07-30"
    assert payload["opportunity_ready"] is True
    assert payload["contract_id"] == "c1"
    assert json.loads(
        result.to_json()
    )["opportunity_status"] == "READY"

    semantic = result.semantic_dict()
    assert "opportunity_id" not in semantic
    assert "created_at" not in semantic


def test_metadata_is_copied_and_json_safe():
    metadata = {"source": "test"}
    result = make_opportunity(metadata=metadata)
    metadata["source"] = "changed"

    assert result.metadata == {"source": "test"}
    assert json.dumps(
        result.to_dict(),
        allow_nan=False,
    )


def test_unsafe_metadata_rejected():
    with pytest.raises(ValueError):
        make_opportunity(
            metadata={"bad": object()}
        )
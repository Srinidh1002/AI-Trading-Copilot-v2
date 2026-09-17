import json
from datetime import date, datetime, timezone

import pytest

from services.contracts.option_contract_candidate_v1 import (
    OptionContractCandidateV1,
)
from services.contracts.option_contract_v1 import OptionContractV1


NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)


def make_contract(**changes):
    values = dict(
        contract_id="c1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        trading_symbol="NIFTY-CALL",
        option_type="CALL",
        strike=25000,
        expiry_date=date(2026, 7, 30),
        lot_size=25,
        market_timestamp=NOW,
        last_price=100,
        bid_price=99,
        ask_price=101,
        open_interest=1000,
        volume=500,
        implied_volatility=18,
    )
    values.update(changes)
    return OptionContractV1(**values)


def make_candidate(**changes):
    values = dict(
        contract=make_contract(),
        candidate_status="ELIGIBLE",
        moneyness="ATM",
        strike_distance_percent=0.0,
        spread_percent=2.0,
        liquidity_score=0.7,
        proximity_score=1.0,
        open_interest_score=0.5,
        volume_score=0.5,
        spread_score=0.5,
        implied_volatility_score=0.5,
        intelligence_alignment_score=1.0,
        total_score=0.7,
    )
    values.update(changes)
    return OptionContractCandidateV1(**values)


def test_valid_eligible_candidate():
    result = make_candidate()

    assert result.eligible is True
    assert result.schema_version == "option_contract_candidate.v1"
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_valid_eligible_with_warnings():
    result = make_candidate(
        candidate_status="ELIGIBLE_WITH_WARNINGS",
        warnings=("IV unavailable",),
    )

    assert result.eligible is True
    assert result.warnings == ("IV UNAVAILABLE",)


def test_valid_rejected_candidate():
    result = make_candidate(
        candidate_status="REJECTED",
        total_score=0.0,
        rejection_reasons=("Volume too low",),
    )

    assert result.eligible is False
    assert result.rejection_reasons == ("VOLUME TOO LOW",)


@pytest.mark.parametrize(
    "field,value",
    [
        ("candidate_status", "UNKNOWN"),
        ("moneyness", "NEAR_ATM"),
        ("strike_distance_percent", -1),
        ("strike_distance_percent", float("nan")),
        ("spread_percent", -1),
        ("liquidity_score", -0.1),
        ("liquidity_score", 1.1),
        ("total_score", -0.1),
        ("total_score", 1.1),
    ],
)
def test_invalid_values(field, value):
    with pytest.raises((TypeError, ValueError)):
        make_candidate(**{field: value})


def test_contract_must_be_canonical_contract():
    with pytest.raises(TypeError):
        make_candidate(contract={})


def test_eligible_candidate_cannot_have_rejection_reasons():
    with pytest.raises(ValueError):
        make_candidate(
            rejection_reasons=("bad",),
        )


def test_plain_eligible_candidate_cannot_have_warnings():
    with pytest.raises(ValueError):
        make_candidate(
            warnings=("warning",),
        )


def test_eligible_with_warnings_requires_warning():
    with pytest.raises(ValueError):
        make_candidate(
            candidate_status="ELIGIBLE_WITH_WARNINGS",
        )


@pytest.mark.parametrize(
    "status",
    ["REJECTED", "MALFORMED", "FAILED"],
)
def test_ineligible_status_requires_rejection_reason(status):
    with pytest.raises(ValueError):
        make_candidate(
            candidate_status=status,
            total_score=0.0,
        )


@pytest.mark.parametrize(
    "status",
    ["REJECTED", "MALFORMED", "FAILED"],
)
def test_ineligible_status_requires_zero_score(status):
    with pytest.raises(ValueError):
        make_candidate(
            candidate_status=status,
            total_score=0.1,
            rejection_reasons=("bad",),
        )


def test_duplicate_reasons_are_rejected():
    with pytest.raises(ValueError):
        make_candidate(
            candidate_status="REJECTED",
            total_score=0.0,
            rejection_reasons=("bad", "BAD"),
        )


def test_serialization_is_primitive_only():
    result = make_candidate()
    payload = result.to_dict()

    assert payload["contract"]["contract_id"] == "c1"
    assert payload["eligible"] is True
    assert payload["rejection_reasons"] == []
    assert payload["warnings"] == []
    assert json.dumps(payload, allow_nan=False)
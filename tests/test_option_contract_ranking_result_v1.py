import json
from datetime import date, datetime, timezone

import pytest

from services.contracts.option_contract_candidate_v1 import (
    OptionContractCandidateV1,
)
from services.contracts.option_contract_ranking_result_v1 import (
    OptionContractRankingResultV1,
)
from services.contracts.option_contract_v1 import OptionContractV1


NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)


def make_contract(
    contract_id="c1",
    strike=25000,
    option_type="CALL",
    underlying_symbol="NIFTY",
    exchange="NSE",
):
    return OptionContractV1(
        contract_id=contract_id,
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        trading_symbol=f"{contract_id}-SYMBOL",
        option_type=option_type,
        strike=strike,
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


def make_candidate(
    contract_id="c1",
    strike=25000,
    score=0.8,
    status="ELIGIBLE",
    option_type="CALL",
    rejection_reasons=(),
    warnings=(),
):
    return OptionContractCandidateV1(
        contract=make_contract(
            contract_id=contract_id,
            strike=strike,
            option_type=option_type,
        ),
        candidate_status=status,
        moneyness="ATM",
        strike_distance_percent=abs(strike - 25000) / 25000 * 100,
        spread_percent=2.0,
        liquidity_score=0.8 if status.startswith("ELIGIBLE") else 0.0,
        proximity_score=0.9 if status.startswith("ELIGIBLE") else 0.0,
        open_interest_score=0.5 if status.startswith("ELIGIBLE") else 0.0,
        volume_score=0.5 if status.startswith("ELIGIBLE") else 0.0,
        spread_score=0.6 if status.startswith("ELIGIBLE") else 0.0,
        implied_volatility_score=0.5 if status.startswith("ELIGIBLE") else 0.0,
        intelligence_alignment_score=0.8 if status.startswith("ELIGIBLE") else 0.0,
        total_score=score if status.startswith("ELIGIBLE") else 0.0,
        rejection_reasons=rejection_reasons,
        warnings=warnings,
    )


def make_result(**changes):
    values = dict(
        ranking_id="r1",
        ranked_at=NOW,
        universe_id="u1",
        intelligence_result_id="i1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        directional_bias="BULLISH",
        required_option_type="CALL",
        ranking_status="RANKED",
        ranked_candidates=(make_candidate(),),
    )
    values.update(changes)
    return OptionContractRankingResultV1(**values)


def test_valid_ranked_result():
    result = make_result()

    assert result.selected_candidate.contract.contract_id == "c1"
    assert result.eligible_candidate_count == 1
    assert result.rejected_candidate_count == 0
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_ranked_with_warnings():
    candidate = make_candidate(
        status="ELIGIBLE_WITH_WARNINGS",
        warnings=("iv unavailable",),
    )
    result = make_result(
        ranking_status="RANKED_WITH_WARNINGS",
        ranked_candidates=(candidate,),
        warnings=("iv unavailable",),
    )

    assert result.ranking_status == "RANKED_WITH_WARNINGS"
    assert result.warnings == ("IV UNAVAILABLE",)


def test_no_eligible_contracts():
    rejected = make_candidate(
        status="REJECTED",
        score=0,
        rejection_reasons=("volume low",),
    )
    result = make_result(
        ranking_status="NO_ELIGIBLE_CONTRACTS",
        ranked_candidates=(),
        rejected_candidates=(rejected,),
    )

    assert result.selected_candidate is None
    assert result.rejected_candidate_count == 1


@pytest.mark.parametrize(
    "status",
    ["BLOCKED", "INSUFFICIENT_DATA", "FAILED"],
)
def test_blocking_statuses_require_blockers(status):
    result = make_result(
        ranking_status=status,
        ranked_candidates=(),
        blockers=("blocked",),
    )

    assert result.blockers == ("BLOCKED",)


@pytest.mark.parametrize(
    "status",
    ["BLOCKED", "INSUFFICIENT_DATA", "FAILED"],
)
def test_blocking_status_without_blockers_rejected(status):
    with pytest.raises(ValueError):
        make_result(
            ranking_status=status,
            ranked_candidates=(),
        )


def test_ranked_requires_candidate():
    with pytest.raises(ValueError):
        make_result(ranked_candidates=())


def test_ranked_cannot_have_warnings():
    with pytest.raises(ValueError):
        make_result(warnings=("warning",))


def test_ranked_with_warnings_requires_warning():
    with pytest.raises(ValueError):
        make_result(
            ranking_status="RANKED_WITH_WARNINGS"
        )


def test_ranked_candidates_must_be_eligible():
    rejected = make_candidate(
        status="REJECTED",
        score=0,
        rejection_reasons=("bad",),
    )

    with pytest.raises(ValueError):
        make_result(ranked_candidates=(rejected,))


def test_rejected_candidates_must_be_ineligible():
    with pytest.raises(ValueError):
        make_result(
            rejected_candidates=(make_candidate(),)
        )


def test_same_contract_cannot_be_ranked_and_rejected():
    rejected = make_candidate(
        status="REJECTED",
        score=0,
        rejection_reasons=("bad",),
    )

    with pytest.raises(ValueError):
        make_result(
            rejected_candidates=(rejected,)
        )


def test_bias_and_option_type_must_match():
    with pytest.raises(ValueError):
        make_result(required_option_type="PUT")


@pytest.mark.parametrize(
    "bias,option_type",
    [
        ("BEARISH", "PUT"),
        ("NEUTRAL", None),
        ("MIXED", None),
        ("UNAVAILABLE", None),
    ],
)
def test_valid_bias_option_type_pairs(bias, option_type):
    if bias == "BEARISH":
        candidate = make_candidate(option_type="PUT")
        result = make_result(
            directional_bias=bias,
            required_option_type=option_type,
            ranked_candidates=(candidate,),
        )
        assert result.required_option_type == "PUT"
    else:
        result = make_result(
            directional_bias=bias,
            required_option_type=option_type,
            ranking_status="BLOCKED",
            ranked_candidates=(),
            blockers=("blocked",),
        )
        assert result.required_option_type is None


def test_canonical_order_is_enforced():
    high = make_candidate(
        contract_id="high",
        strike=25000,
        score=0.9,
    )
    low = make_candidate(
        contract_id="low",
        strike=25100,
        score=0.7,
    )

    result = make_result(
        ranked_candidates=(high, low)
    )

    assert result.ranked_candidates == (high, low)

    with pytest.raises(ValueError):
        make_result(
            ranked_candidates=(low, high)
        )


def test_duplicate_contracts_rejected():
    candidate = make_candidate()

    with pytest.raises(ValueError):
        make_result(
            ranked_candidates=(candidate, candidate)
        )


def test_identity_mismatch_rejected():
    candidate = OptionContractCandidateV1(
        contract=make_contract(
            underlying_symbol="SENSEX",
            exchange="BSE",
        ),
        candidate_status="ELIGIBLE",
        moneyness="ATM",
        strike_distance_percent=0,
        spread_percent=2,
        liquidity_score=.8,
        proximity_score=.9,
        open_interest_score=.5,
        volume_score=.5,
        spread_score=.6,
        implied_volatility_score=.5,
        intelligence_alignment_score=.8,
        total_score=.8,
    )

    with pytest.raises(ValueError):
        make_result(ranked_candidates=(candidate,))


def test_serialization_and_semantic_output():
    result = make_result()
    payload = result.to_dict()

    assert payload["selected_contract_id"] == "c1"
    assert payload["eligible_candidate_count"] == 1
    assert payload["rejected_candidate_count"] == 0
    assert json.loads(result.to_json())["ranking_status"] == "RANKED"

    semantic = result.semantic_dict()
    assert "ranking_id" not in semantic
    assert "ranked_at" not in semantic


@pytest.mark.parametrize(
    "field,value",
    [
        ("ranking_id", ""),
        ("ranked_at", datetime(2026, 7, 27)),
        ("underlying_symbol", "NIFTY50"),
        ("exchange", "BSE"),
        ("directional_bias", "UP"),
        ("required_option_type", "CE"),
        ("ranking_status", "UNKNOWN"),
    ],
)
def test_invalid_top_level_values(field, value):
    with pytest.raises((TypeError, ValueError)):
        make_result(**{field: value})


def test_unsafe_metadata_rejected():
    with pytest.raises(ValueError):
        make_result(metadata={"bad": object()})
from datetime import date, datetime, timedelta, timezone

import pytest

from services.contracts.option_contract_ranking_policy_v1 import (
    OptionContractRankingPolicyV1,
)
from services.contracts.option_contract_v1 import OptionContractV1
from services.option_contract_ranking.evaluator import (
    evaluate_option_contract,
)


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
        tradable=True,
    )
    values.update(changes)
    return OptionContractV1(**values)


def evaluate(contract=None, **kwargs):
    return evaluate_option_contract(
        contract or make_contract(),
        spot_price=kwargs.pop("spot_price", 25000),
        required_option_type=kwargs.pop(
            "required_option_type",
            "CALL",
        ),
        now=kwargs.pop("now", NOW),
        policy=kwargs.pop(
            "policy",
            OptionContractRankingPolicyV1(),
        ),
        intelligence_alignment_score=kwargs.pop(
            "intelligence_alignment_score",
            1.0,
        ),
        **kwargs,
    )


def test_valid_contract_is_eligible():
    result = evaluate()

    assert result.eligible is True
    assert result.candidate_status == "ELIGIBLE"
    assert result.moneyness == "ATM"
    assert 0 < result.total_score <= 1


def test_call_moneyness():
    assert evaluate(
        make_contract(strike=24900)
    ).moneyness == "ITM"

    assert evaluate(
        make_contract(strike=25100)
    ).moneyness == "OTM"


def test_put_moneyness():
    assert evaluate(
        make_contract(
            option_type="PUT",
            strike=25100,
        ),
        required_option_type="PUT",
    ).moneyness == "ITM"

    assert evaluate(
        make_contract(
            option_type="PUT",
            strike=24900,
        ),
        required_option_type="PUT",
    ).moneyness == "OTM"


@pytest.mark.parametrize(
    "changes,reason",
    [
        (
            {"option_type": "PUT"},
            "OPTION TYPE DOES NOT MATCH DIRECTIONAL BIAS",
        ),
        (
            {"tradable": False},
            "CONTRACT IS NOT TRADABLE",
        ),
        (
            {"expiry_date": date(2026, 7, 26)},
            "CONTRACT IS EXPIRED",
        ),
        (
            {
                "market_timestamp": (
                    NOW - timedelta(seconds=301)
                )
            },
            "CONTRACT QUOTE IS STALE",
        ),
        (
            {
                "market_timestamp": (
                    NOW + timedelta(seconds=6)
                )
            },
            "CONTRACT TIMESTAMP IS IN THE FUTURE",
        ),
        (
            {"strike": 27000},
            "STRIKE DISTANCE EXCEEDS POLICY LIMIT",
        ),
        (
            {"bid_price": None},
            "BID AND ASK ARE REQUIRED",
        ),
        (
            {"bid_price": 0},
            "BID AND ASK MUST BE POSITIVE",
        ),
        (
            {
                "bid_price": 105,
                "ask_price": 100,
            },
            "ASK PRICE IS BELOW BID PRICE",
        ),
        (
            {
                "bid_price": 90,
                "ask_price": 110,
            },
            "BID-ASK SPREAD EXCEEDS POLICY LIMIT",
        ),
        (
            {"volume": None},
            "VOLUME IS REQUIRED",
        ),
        (
            {"volume": 99},
            "VOLUME IS BELOW POLICY MINIMUM",
        ),
        (
            {"open_interest": None},
            "OPEN INTEREST IS REQUIRED",
        ),
        (
            {"open_interest": 499},
            "OPEN INTEREST IS BELOW POLICY MINIMUM",
        ),
    ],
)
def test_hard_rejections(changes, reason):
    result = evaluate(make_contract(**changes))

    assert result.eligible is False
    assert result.candidate_status == "REJECTED"
    assert result.total_score == 0
    assert reason in result.rejection_reasons


def test_missing_iv_warns_when_not_required():
    result = evaluate(
        make_contract(implied_volatility=None)
    )

    assert result.candidate_status == (
        "ELIGIBLE_WITH_WARNINGS"
    )
    assert (
        "IMPLIED VOLATILITY IS UNAVAILABLE"
        in result.warnings
    )


def test_missing_iv_rejects_when_required():
    policy = OptionContractRankingPolicyV1(
        require_implied_volatility=True
    )

    result = evaluate(
        make_contract(implied_volatility=None),
        policy=policy,
    )

    assert result.eligible is False
    assert (
        "IMPLIED VOLATILITY IS REQUIRED"
        in result.rejection_reasons
    )


def test_iv_outside_range_rejected():
    policy = OptionContractRankingPolicyV1(
        minimum_implied_volatility=10,
        maximum_implied_volatility=30,
    )

    result = evaluate(
        make_contract(implied_volatility=40),
        policy=policy,
    )

    assert (
        "IMPLIED VOLATILITY IS OUTSIDE POLICY RANGE"
        in result.rejection_reasons
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("spot_price", 0),
        ("spot_price", -1),
        ("spot_price", float("nan")),
        ("required_option_type", "CE"),
        ("intelligence_alignment_score", -0.1),
        ("intelligence_alignment_score", 1.1),
    ],
)
def test_invalid_inputs(field, value):
    kwargs = {field: value}

    with pytest.raises((TypeError, ValueError)):
        evaluate(**kwargs)


def test_now_must_be_timezone_aware():
    with pytest.raises(ValueError):
        evaluate(
            now=datetime(2026, 7, 27)
        )


def test_policy_type_is_enforced():
    with pytest.raises(TypeError):
        evaluate_option_contract(
            make_contract(),
            spot_price=25000,
            required_option_type="CALL",
            now=NOW,
            policy=object(),
        )


def test_optional_liquidity_fields_produce_warnings():
    policy = OptionContractRankingPolicyV1(
        require_bid_ask=False,
        require_volume=False,
        require_open_interest=False,
    )

    result = evaluate(
        make_contract(
            bid_price=None,
            ask_price=None,
            volume=None,
            open_interest=None,
        ),
        policy=policy,
    )

    assert result.eligible is True
    assert result.candidate_status == (
        "ELIGIBLE_WITH_WARNINGS"
    )
    assert "SPREAD IS UNAVAILABLE" in result.warnings
    assert "VOLUME IS UNAVAILABLE" in result.warnings
    assert "OPEN INTEREST IS UNAVAILABLE" in result.warnings


def test_alignment_score_affects_total_score():
    high = evaluate(
        intelligence_alignment_score=1.0
    )
    low = evaluate(
        intelligence_alignment_score=0.0
    )

    assert high.total_score > low.total_score


def test_better_liquidity_scores_higher():
    strong = evaluate(
        make_contract(
            bid_price=99.5,
            ask_price=100.5,
            volume=5000,
            open_interest=5000,
        )
    )
    weak = evaluate(
        make_contract(
            bid_price=98,
            ask_price=102,
            volume=100,
            open_interest=500,
        )
    )

    assert strong.total_score > weak.total_score
    assert strong.liquidity_score > weak.liquidity_score
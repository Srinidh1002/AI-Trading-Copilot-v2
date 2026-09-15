import pytest

from services.option_full_response_validator import (
    OptionFullResponseValidationError,
    validate_option_full_response,
    validate_option_full_response_partial,
)


def item(
    token="1",
    *,
    exchange="NFO",
    ltp=100.0,
    bid=99.0,
    ask=101.0,
    volume=10,
    open_interest=20,
):
    return {
        "exchange": exchange,
        "symbolToken": token,
        "ltp": ltp,
        "tradeVolume": volume,
        "opnInterest": open_interest,
        "depth": {
            "buy": [{"price": bid}],
            "sell": [{"price": ask}],
        },
    }


def response(
    *,
    fetched=None,
    unfetched=None,
    status=True,
):
    return {
        "status": status,
        "data": {
            "fetched": (
                [item()]
                if fetched is None
                else fetched
            ),
            "unfetched": (
                []
                if unfetched is None
                else unfetched
            ),
        },
    }


def test_valid_exact_response():
    result = validate_option_full_response(
        response=response(),
        option_exchange="NFO",
        requested_tokens=["1"],
    )

    assert list(result) == ["1"]
    assert result["1"]["_validated_ltp"] == 100.0
    assert result["1"]["_validated_bid"] == 99.0
    assert result["1"]["_validated_ask"] == 101.0
    assert result["1"]["_validated_volume"] == 10
    assert (
        result["1"]["_validated_open_interest"]
        == 20
    )


@pytest.mark.parametrize(
    "bad_response",
    (
        None,
        {},
        {"status": False, "data": {}},
        {"status": True, "data": None},
        {
            "status": True,
            "data": {
                "fetched": None,
                "unfetched": [],
            },
        },
    ),
)
def test_invalid_envelope_fails_closed(
    bad_response,
):
    with pytest.raises(
        OptionFullResponseValidationError
    ):
        validate_option_full_response(
            response=bad_response,
            option_exchange="NFO",
            requested_tokens=["1"],
        )


def test_missing_requested_token_fails_closed():
    with pytest.raises(
        OptionFullResponseValidationError,
        match="missing requested tokens",
    ):
        validate_option_full_response(
            response=response(
                fetched=[
                    item("1"),
                ]
            ),
            option_exchange="NFO",
            requested_tokens=[
                "1",
                "2",
            ],
        )


def test_unfetched_requested_token_fails_closed():
    with pytest.raises(
        OptionFullResponseValidationError,
        match="was unfetched",
    ):
        validate_option_full_response(
            response=response(
                fetched=[],
                unfetched=[
                    {
                        "exchange": "NFO",
                        "symbolToken": "1",
                        "message": "not available",
                    }
                ],
            ),
            option_exchange="NFO",
            requested_tokens=["1"],
        )


def test_duplicate_fetched_token_fails_closed():
    with pytest.raises(
        OptionFullResponseValidationError,
        match="duplicate fetched token",
    ):
        validate_option_full_response(
            response=response(
                fetched=[
                    item("1"),
                    item("1"),
                ]
            ),
            option_exchange="NFO",
            requested_tokens=["1"],
        )


def test_unexpected_exchange_or_token_fails_closed():
    with pytest.raises(
        OptionFullResponseValidationError,
        match="unexpected fetched identity",
    ):
        validate_option_full_response(
            response=response(
                fetched=[
                    item(
                        "1",
                        exchange="BFO",
                    )
                ]
            ),
            option_exchange="NFO",
            requested_tokens=["1"],
        )


@pytest.mark.parametrize(
    "changes",
    (
        {"ltp": 0},
        {"ltp": float("nan")},
        {"bid": 0},
        {"ask": 0},
        {"bid": 102, "ask": 101},
        {"volume": -1},
        {"volume": 1.5},
        {"open_interest": -1},
        {"open_interest": 1.5},
    ),
)
def test_invalid_market_values_fail_closed(
    changes,
):
    with pytest.raises(
        OptionFullResponseValidationError
    ):
        validate_option_full_response(
            response=response(
                fetched=[
                    item(**changes)
                ]
            ),
            option_exchange="NFO",
            requested_tokens=["1"],
        )


def test_result_is_defensive_copy():
    payload = response()

    result = validate_option_full_response(
        response=payload,
        option_exchange="NFO",
        requested_tokens=["1"],
    )

    result["1"]["ltp"] = 999

    assert payload["data"]["fetched"][0]["ltp"] == 100.0


def test_fetched_exchange_may_be_omitted():
    payload = response()

    payload[
        "data"
    ][
        "fetched"
    ][0].pop(
        "exchange"
    )

    result = validate_option_full_response(
        response=payload,
        option_exchange="NFO",
        requested_tokens=["1"],
    )

    assert list(result) == ["1"]


def test_supplied_mismatched_exchange_fails_closed():
    with pytest.raises(
        OptionFullResponseValidationError,
        match="unexpected fetched identity",
    ):
        validate_option_full_response(
            response=response(
                fetched=[
                    item(
                        "1",
                        exchange="BFO",
                    )
                ]
            ),
            option_exchange="NFO",
            requested_tokens=["1"],
        )


def test_partial_validation_retains_valid_sibling_when_one_is_unfetched():
    result = validate_option_full_response_partial(
        response=response(
            fetched=[item("1")],
            unfetched=[
                {
                    "exchange": "NFO",
                    "symbolToken": "2",
                    "message": "not available",
                }
            ],
        ),
        option_exchange="NFO",
        requested_tokens=["1", "2"],
    )

    assert tuple(result.validated_by_token) == ("1",)
    assert result.unfetched_tokens == ("2",)
    assert result.malformed_tokens == ()


def test_partial_validation_retains_valid_sibling_when_one_is_malformed():
    result = validate_option_full_response_partial(
        response=response(
            fetched=[
                item("1"),
                item("2", ltp=0),
            ],
        ),
        option_exchange="NFO",
        requested_tokens=["1", "2"],
    )

    assert tuple(result.validated_by_token) == ("1",)
    assert result.unfetched_tokens == ()
    assert result.malformed_tokens == ("2",)


def test_partial_validation_classifies_absent_requested_token_as_unfetched():
    result = validate_option_full_response_partial(
        response=response(
            fetched=[item("1")],
            unfetched=[],
        ),
        option_exchange="NFO",
        requested_tokens=["1", "2"],
    )

    assert tuple(result.validated_by_token) == ("1",)
    assert result.unfetched_tokens == ("2",)
    assert result.malformed_tokens == ()


def test_partial_validation_can_return_zero_valid_contracts():
    result = validate_option_full_response_partial(
        response=response(
            fetched=[item("1", ltp=0)],
            unfetched=[
                {
                    "exchange": "NFO",
                    "symbolToken": "2",
                    "message": "not available",
                }
            ],
        ),
        option_exchange="NFO",
        requested_tokens=["1", "2"],
    )

    assert result.validated_by_token == {}
    assert result.unfetched_tokens == ("2",)
    assert result.malformed_tokens == ("1",)


def test_partial_validation_still_fails_on_unexpected_identity():
    with pytest.raises(
        OptionFullResponseValidationError,
        match="unexpected fetched identity",
    ):
        validate_option_full_response_partial(
            response=response(
                fetched=[item("999")],
                unfetched=[],
            ),
            option_exchange="NFO",
            requested_tokens=["1"],
        )


def test_task91043_zero_market_prices_remain_strictly_malformed_by_default():
    response = {
        "status": True,
        "data": {
            "fetched": [
                {
                    "exchange": "NFO",
                    "symbolToken": "ZERO",
                    "ltp": 0.0,
                    "tradeVolume": 0,
                    "opnInterest": 800,
                    "depth": {
                        "buy": [{"price": 0.0}],
                        "sell": [{"price": 0.05}],
                    },
                },
            ],
            "unfetched": [],
        },
    }

    result = validate_option_full_response_partial(
        response=response,
        option_exchange="NFO",
        requested_tokens=("ZERO",),
    )

    assert result.validated_by_token == {}
    assert result.unfetched_tokens == ()
    assert result.malformed_tokens == ("ZERO",)


def test_task91043_chain_evidence_mode_preserves_zero_market_prices():
    response = {
        "status": True,
        "data": {
            "fetched": [
                {
                    "exchange": "NFO",
                    "symbolToken": "ZERO",
                    "ltp": 0.0,
                    "tradeVolume": 0,
                    "opnInterest": 800,
                    "depth": {
                        "buy": [{"price": 0.0}],
                        "sell": [{"price": 0.05}],
                    },
                },
            ],
            "unfetched": [],
        },
    }

    result = validate_option_full_response_partial(
        response=response,
        option_exchange="NFO",
        requested_tokens=("ZERO",),
        allow_zero_market_prices=True,
    )

    assert result.unfetched_tokens == ()
    assert result.malformed_tokens == ()
    assert tuple(result.validated_by_token) == ("ZERO",)

    quote = result.validated_by_token["ZERO"]

    assert quote["_validated_ltp"] == 0.0
    assert quote["_validated_bid"] == 0.0
    assert quote["_validated_ask"] == 0.05
    assert quote["_validated_open_interest"] == 800

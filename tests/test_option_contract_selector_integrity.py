"""
Integrity and safety tests for the option contract selector.

These tests verify that:
- Bullish direction selects CE contracts.
- Bearish direction selects PE contracts.
- Invalid direction fails safely.
- Invalid market data is rejected.
- Wide spreads are rejected.
- Low volume is rejected.
- Low open interest is rejected.
- Delta filtering works when enabled.
- Missing delta is allowed when optional.
- Actual exchange lot size is preserved.
- The best liquid near-ATM contract is selected.

Read-only.
No orders are placed.
"""

import pytest

from services.option_contract_selector import (
    select_option_contract,
)


def make_contract(
    symbol="NIFTY14JUL2624200CE",
    strike=24200,
    option_type="CE",
    premium=150.0,
    bid=149.5,
    ask=150.5,
    volume=20000,
    open_interest=30000,
    delta=None,
    lot_size=75,
    expiry="14JUL2026",
):
    """
    Create a normalized option contract
    for selector tests.
    """

    return {
        "symbol": symbol,
        "strike": strike,
        "option_type": option_type,
        "expiry": expiry,
        "premium": premium,
        "bid": bid,
        "ask": ask,
        "volume": volume,
        "open_interest": open_interest,
        "delta": delta,
        "lot_size": lot_size,
    }


def test_bullish_direction_selects_ce():

    contracts = [
        make_contract(
            option_type="CE",
        ),
        make_contract(
            symbol="NIFTY14JUL2624200PE",
            option_type="PE",
        ),
    ]

    result = select_option_contract(
        contracts=contracts,
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is True

    assert (
        result["option_type"]
        == "CE"
    )


def test_bearish_direction_selects_pe():

    contracts = [
        make_contract(
            option_type="CE",
        ),
        make_contract(
            symbol="NIFTY14JUL2624200PE",
            option_type="PE",
        ),
    ]

    result = select_option_contract(
        contracts=contracts,
        direction="BEARISH",
        spot_price=24206,
    )

    assert result["selected"] is True

    assert (
        result["option_type"]
        == "PE"
    )


def test_invalid_direction_returns_no_contract():

    result = select_option_contract(
        contracts=[
            make_contract()
        ],
        direction="NEUTRAL",
        spot_price=24206,
    )

    assert result["selected"] is False

    assert (
        result["decision"]
        == "NO_CONTRACT"
    )


def test_empty_contracts_return_no_contract():

    result = select_option_contract(
        contracts=[],
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is False

    assert (
        result["decision"]
        == "NO_CONTRACT"
    )


def test_invalid_spot_price_is_rejected():

    with pytest.raises(
        ValueError,
        match=(
            "Spot price must be "
            "greater than zero"
        ),
    ):
        select_option_contract(
            contracts=[
                make_contract()
            ],
            direction="BULLISH",
            spot_price=0,
        )


def test_zero_premium_is_rejected():

    result = select_option_contract(
        contracts=[
            make_contract(
                premium=0,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is False


def test_zero_bid_is_rejected():

    result = select_option_contract(
        contracts=[
            make_contract(
                bid=0,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is False


def test_zero_ask_is_rejected():

    result = select_option_contract(
        contracts=[
            make_contract(
                ask=0,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is False


def test_ask_below_bid_is_rejected():

    result = select_option_contract(
        contracts=[
            make_contract(
                bid=151,
                ask=150,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is False


def test_wide_spread_is_rejected():

    result = select_option_contract(
        contracts=[
            make_contract(
                bid=140,
                ask=160,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
        maximum_spread_percent=2.0,
    )

    assert result["selected"] is False


def test_low_volume_is_rejected():

    result = select_option_contract(
        contracts=[
            make_contract(
                volume=50,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
        minimum_volume=100,
    )

    assert result["selected"] is False


def test_low_open_interest_is_rejected():

    result = select_option_contract(
        contracts=[
            make_contract(
                open_interest=100,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
        minimum_open_interest=500,
    )

    assert result["selected"] is False


def test_missing_delta_allowed_when_optional():

    result = select_option_contract(
        contracts=[
            make_contract(
                delta=None,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
        require_delta=False,
    )

    assert result["selected"] is True


def test_missing_delta_rejected_when_required():

    result = select_option_contract(
        contracts=[
            make_contract(
                delta=None,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
        require_delta=True,
    )

    assert result["selected"] is False


def test_delta_outside_required_range_is_rejected():

    result = select_option_contract(
        contracts=[
            make_contract(
                delta=0.10,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
        minimum_delta=0.30,
        maximum_delta=0.75,
        require_delta=True,
    )

    assert result["selected"] is False


def test_valid_delta_is_accepted_when_required():

    result = select_option_contract(
        contracts=[
            make_contract(
                delta=0.55,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
        require_delta=True,
    )

    assert result["selected"] is True


def test_negative_pe_delta_is_normalized_by_absolute_value():

    result = select_option_contract(
        contracts=[
            make_contract(
                symbol="NIFTY14JUL2624200PE",
                option_type="PE",
                delta=-0.55,
            )
        ],
        direction="BEARISH",
        spot_price=24206,
        require_delta=True,
    )

    assert result["selected"] is True

    assert (
        result["option_type"]
        == "PE"
    )


def test_actual_lot_size_is_preserved():

    result = select_option_contract(
        contracts=[
            make_contract(
                lot_size=75,
            )
        ],
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is True

    assert (
        result["lot_size"]
        == 75
    )


def test_string_lot_size_is_normalized():

    result = select_option_contract(
        contracts=[
            make_contract(
                lot_size="75.0",
            )
        ],
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is True

    assert (
        result["lot_size"]
        == 75
    )


def test_selector_prefers_better_scoring_contract():

    contracts = [
        make_contract(
            symbol="NIFTY14JUL2624000CE",
            strike=24000,
            bid=149,
            ask=151,
            volume=1000,
            open_interest=2000,
        ),
        make_contract(
            symbol="NIFTY14JUL2624200CE",
            strike=24200,
            bid=149.8,
            ask=150.2,
            volume=20000,
            open_interest=30000,
        ),
    ]

    result = select_option_contract(
        contracts=contracts,
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is True

    assert (
        result["symbol"]
        == "NIFTY14JUL2624200CE"
    )


def test_wrong_option_type_is_ignored():

    result = select_option_contract(
        contracts=[
            make_contract(
                symbol="NIFTY14JUL2624200PE",
                option_type="PE",
            )
        ],
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is False

    assert (
        result["option_type"]
        == "CE"
    )


def test_selected_contract_contains_score_and_reasons():

    result = select_option_contract(
        contracts=[
            make_contract()
        ],
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is True

    assert result["score"] > 0

    assert isinstance(
        result["reasons"],
        list,
    )

    assert result["reasons"]
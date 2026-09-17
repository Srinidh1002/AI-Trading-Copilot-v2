"""Tests for deterministic option-chain IV-skew intelligence."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)
from services.contracts.option_chain_snapshot_v1 import (
    OptionChainSnapshotV1,
)
from services.contracts.option_quote_v1 import OptionQuoteV1
from services.contracts.option_strike_row_v1 import OptionStrikeRowV1
from services.option_chain_intelligence.iv_skew import (
    IV_SKEW_METRIC_NAME,
    calculate_iv_skew,
)


CREATED_AT = datetime(
    2026,
    1,
    1,
    10,
    0,
    tzinfo=timezone.utc,
)
EXPIRY = date(2026, 1, 29)


def make_quote(
    *,
    quote_id: str,
    strike: float,
    option_type: str,
    implied_volatility: float | None,
    symbol: str = "NIFTY",
    exchange: str = "NSE",
) -> OptionQuoteV1:
    return OptionQuoteV1(
        option_quote_id=quote_id,
        created_at=CREATED_AT,
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        strike=strike,
        option_type=option_type,
        ltp=100.0,
        bid_price=99.0,
        ask_price=101.0,
        bid_quantity=10,
        ask_quantity=10,
        volume=100,
        open_interest=1000,
        change_in_open_interest=10,
        implied_volatility=implied_volatility,
        underlying_value=22000.0,
        source_timestamp=CREATED_AT,
        is_complete=True,
        provider_name="TEST",
        source_record_id=quote_id,
        blockers=(),
        warnings=(),
        execution_mode="PAPER",
        live_execution_eligible=False,
    )


def make_row(
    *,
    row_id: str,
    strike: float,
    call_iv: float | None = 15.0,
    put_iv: float | None = 15.0,
    include_call: bool = True,
    include_put: bool = True,
    symbol: str = "NIFTY",
    exchange: str = "NSE",
) -> OptionStrikeRowV1:
    return OptionStrikeRowV1(
        strike_row_id=row_id,
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        strike=strike,
        call=(
            make_quote(
                quote_id=f"{row_id}-call",
                strike=strike,
                option_type="CALL",
                implied_volatility=call_iv,
                symbol=symbol,
                exchange=exchange,
            )
            if include_call
            else None
        ),
        put=(
            make_quote(
                quote_id=f"{row_id}-put",
                strike=strike,
                option_type="PUT",
                implied_volatility=put_iv,
                symbol=symbol,
                exchange=exchange,
            )
            if include_put
            else None
        ),
        blockers=(),
        warnings=(),
    )


def make_snapshot(
    rows: tuple[OptionStrikeRowV1, ...],
    *,
    symbol: str = "NIFTY",
    exchange: str = "NSE",
) -> OptionChainSnapshotV1:
    strikes = tuple(row.strike for row in rows)

    return OptionChainSnapshotV1(
        option_chain_snapshot_id="snapshot-1",
        created_at=CREATED_AT,
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        underlying_value=22000.0,
        strike_rows=rows,
        strike_count=len(rows),
        complete_pair_count=sum(
            row.call is not None and row.put is not None
            for row in rows
        ),
        call_only_count=sum(
            row.call is not None and row.put is None
            for row in rows
        ),
        put_only_count=sum(
            row.call is None and row.put is not None
            for row in rows
        ),
        minimum_strike=min(strikes) if strikes else None,
        maximum_strike=max(strikes) if strikes else None,
        source_timestamp=CREATED_AT,
        provider_name="TEST",
        blockers=(),
        warnings=(),
        execution_mode="PAPER",
        live_execution_eligible=False,
    )


def make_policy(**overrides) -> OptionChainIntelligencePolicyV1:
    values = DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY.to_dict()
    values.pop("schema_version")
    values.pop("required_metrics")
    values["metric_weights"] = tuple(
        tuple(item)
        for item in values["metric_weights"]
    )
    values.update(overrides)

    return OptionChainIntelligencePolicyV1(**values)


def test_metric_name_constant() -> None:
    assert IV_SKEW_METRIC_NAME == "IV_SKEW"


def test_basic_bearish_iv_skew() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_iv=14.0,
                put_iv=18.0,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_iv=16.0,
                put_iv=20.0,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.value == 4.0
    assert metric.signal == "BEARISH"
    assert metric.status == "VALID"
    assert metric.sample_size == 4
    assert metric.supporting_strikes == (
        21900.0,
        22000.0,
    )


def test_basic_bullish_iv_skew() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_iv=20.0,
                put_iv=16.0,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_iv=18.0,
                put_iv=14.0,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.value == -4.0
    assert metric.signal == "BULLISH"
    assert metric.status == "VALID"


def test_equal_average_iv_is_neutral() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_iv=15.0,
                put_iv=16.0,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_iv=17.0,
                put_iv=16.0,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.value == 0.0
    assert metric.signal == "NEUTRAL"


@pytest.mark.parametrize(
    ("difference", "expected_signal"),
    (
        (3.0, "BEARISH"),
        (2.0, "BEARISH"),
        (1.99, "NEUTRAL"),
        (0.0, "NEUTRAL"),
        (-1.99, "NEUTRAL"),
        (-2.0, "BULLISH"),
        (-3.0, "BULLISH"),
    ),
)
def test_signal_threshold_classification(
    difference: float,
    expected_signal: str,
) -> None:
    call_iv = 15.0
    put_iv = call_iv + difference

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_iv=call_iv,
                put_iv=put_iv,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.value == pytest.approx(difference)
    assert metric.signal == expected_signal


def test_custom_material_difference_is_used() -> None:
    policy = make_policy(
        iv_skew_material_difference=5.0
    )

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_iv=15.0,
                put_iv=19.0,
            ),
        )
    )

    metric = calculate_iv_skew(
        snapshot=snapshot,
        policy=policy,
    )

    assert metric.value == 4.0
    assert metric.signal == "NEUTRAL"


def test_exact_custom_material_difference_is_directional() -> None:
    policy = make_policy(
        iv_skew_material_difference=5.0
    )

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_iv=15.0,
                put_iv=20.0,
            ),
        )
    )

    metric = calculate_iv_skew(
        snapshot=snapshot,
        policy=policy,
    )

    assert metric.value == 5.0
    assert metric.signal == "BEARISH"


def test_missing_call_iv_uses_available_put_iv_but_requires_both_sides() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_iv=None,
                put_iv=18.0,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.value is None
    assert metric.signal == "UNAVAILABLE"
    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 1


def test_missing_put_iv_requires_both_sides() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_iv=15.0,
                put_iv=None,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.value is None
    assert metric.signal == "UNAVAILABLE"
    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 1


def test_partial_missing_values_use_available_observations() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_iv=None,
                put_iv=20.0,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_iv=15.0,
                put_iv=19.0,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.value == 4.5
    assert metric.signal == "BEARISH"
    assert metric.sample_size == 3
    assert metric.supporting_strikes == (
        21900.0,
        22000.0,
    )


def test_empty_chain_is_unavailable() -> None:
    metric = calculate_iv_skew(
        snapshot=make_snapshot(())
    )

    assert metric.value is None
    assert metric.signal == "UNAVAILABLE"
    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 0


def test_all_missing_iv_is_unavailable() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_iv=None,
                put_iv=None,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 0
    assert metric.supporting_strikes == ()


def test_call_only_chain_is_unavailable() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_iv=15.0,
                include_put=False,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 1


def test_put_only_chain_is_unavailable() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                put_iv=18.0,
                include_call=False,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 1


def test_zero_iv_values_are_counted() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_iv=0.0,
                put_iv=2.0,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.value == 2.0
    assert metric.signal == "BEARISH"
    assert metric.sample_size == 2


def test_parameters_reconcile() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_iv=14.0,
                put_iv=18.0,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_iv=16.0,
                put_iv=20.0,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)
    parameters = dict(metric.parameters)

    assert parameters["average_call_iv"] == 15.0
    assert parameters["average_put_iv"] == 19.0
    assert parameters["call_sample_count"] == 2
    assert parameters["put_sample_count"] == 2
    assert parameters["material_difference"] == 2.0


def test_supporting_strikes_include_used_rows_only() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_iv=None,
                put_iv=None,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_iv=15.0,
                put_iv=18.0,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.supporting_strikes == (22000.0,)


def test_supporting_strikes_are_sorted() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_iv=15.0,
                put_iv=18.0,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_iv=15.0,
                put_iv=18.0,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_iv=15.0,
                put_iv=18.0,
            ),
        )
    )

    metric = calculate_iv_skew(snapshot=snapshot)

    assert metric.supporting_strikes == (
        21900.0,
        22000.0,
        22100.0,
    )


def test_snapshot_type_validation() -> None:
    with pytest.raises(TypeError):
        calculate_iv_skew(snapshot="snapshot")


def test_policy_type_validation() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
            ),
        )
    )

    with pytest.raises(TypeError):
        calculate_iv_skew(
            snapshot=snapshot,
            policy="policy",
        )


def test_snapshot_is_not_mutated() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_iv=15.0,
                put_iv=18.0,
            ),
        )
    )

    before = snapshot.to_dict()

    calculate_iv_skew(snapshot=snapshot)

    assert snapshot.to_dict() == before


@pytest.mark.parametrize(
    ("symbol", "exchange"),
    (
        ("NIFTY", "NSE"),
        ("BANKNIFTY", "NSE"),
        ("FINNIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ),
)
def test_four_market_compatibility(
    symbol: str,
    exchange: str,
) -> None:
    rows = (
        make_row(
            row_id="row-1",
            strike=22000.0,
            call_iv=15.0,
            put_iv=19.0,
            symbol=symbol,
            exchange=exchange,
        ),
    )

    metric = calculate_iv_skew(
        snapshot=make_snapshot(
            rows,
            symbol=symbol,
            exchange=exchange,
        )
    )

    assert metric.value == 4.0
    assert metric.signal == "BEARISH"


def test_no_decision_or_execution_output() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_iv=15.0,
                put_iv=19.0,
            ),
        )
    )

    serialized = calculate_iv_skew(
        snapshot=snapshot
    ).to_dict()

    assert "action" not in serialized
    assert "decision" not in serialized
    assert "ranking" not in serialized
    assert "risk" not in serialized
    assert "execution" not in serialized
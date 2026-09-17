"""Tests for deterministic option-chain PCR intelligence."""

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
from services.option_chain_intelligence.pcr import (
    PCR_OPEN_INTEREST_METRIC_NAME,
    PCR_VOLUME_METRIC_NAME,
    calculate_open_interest_pcr,
    calculate_pcr_metrics,
    calculate_volume_pcr,
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
    open_interest: int | None = 100,
    volume: int | None = 100,
) -> OptionQuoteV1:
    return OptionQuoteV1(
        option_quote_id=quote_id,
        created_at=CREATED_AT,
        underlying_symbol="NIFTY",
        exchange="NSE",
        expiry=EXPIRY,
        strike=strike,
        option_type=option_type,
        ltp=100.0,
        bid_price=99.0,
        ask_price=101.0,
        bid_quantity=10,
        ask_quantity=10,
        volume=volume,
        open_interest=open_interest,
        change_in_open_interest=10,
        implied_volatility=15.0,
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
    call_oi: int | None = 100,
    put_oi: int | None = 100,
    call_volume: int | None = 100,
    put_volume: int | None = 100,
    include_call: bool = True,
    include_put: bool = True,
) -> OptionStrikeRowV1:
    return OptionStrikeRowV1(
        strike_row_id=row_id,
        underlying_symbol="NIFTY",
        exchange="NSE",
        expiry=EXPIRY,
        strike=strike,
        call=(
            make_quote(
                quote_id=f"{row_id}-call",
                strike=strike,
                option_type="CALL",
                open_interest=call_oi,
                volume=call_volume,
            )
            if include_call
            else None
        ),
        put=(
            make_quote(
                quote_id=f"{row_id}-put",
                strike=strike,
                option_type="PUT",
                open_interest=put_oi,
                volume=put_volume,
            )
            if include_put
            else None
        ),
        blockers=(),
        warnings=(),
    )


def make_snapshot(
    rows: tuple[OptionStrikeRowV1, ...],
) -> OptionChainSnapshotV1:
    complete_pair_count = sum(
        row.call is not None and row.put is not None
        for row in rows
    )
    call_only_count = sum(
        row.call is not None and row.put is None
        for row in rows
    )
    put_only_count = sum(
        row.call is None and row.put is not None
        for row in rows
    )

    strikes = tuple(row.strike for row in rows)

    return OptionChainSnapshotV1(
        option_chain_snapshot_id="snapshot-1",
        created_at=CREATED_AT,
        underlying_symbol="NIFTY",
        exchange="NSE",
        expiry=EXPIRY,
        underlying_value=22000.0,
        strike_rows=rows,
        strike_count=len(rows),
        complete_pair_count=complete_pair_count,
        call_only_count=call_only_count,
        put_only_count=put_only_count,
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


def test_metric_name_constants() -> None:
    assert PCR_OPEN_INTEREST_METRIC_NAME == "PCR_OPEN_INTEREST"
    assert PCR_VOLUME_METRIC_NAME == "PCR_VOLUME"


def test_open_interest_pcr_basic_bullish() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=100,
                put_oi=120,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=100,
                put_oi=120,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.metric_name == "PCR_OPEN_INTEREST"
    assert metric.value == 1.2
    assert metric.signal == "BULLISH"
    assert metric.status == "VALID"
    assert metric.sample_size == 4
    assert metric.supporting_strikes == (
        21900.0,
        22000.0,
    )


def test_volume_pcr_basic_bullish() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_volume=100,
                put_volume=120,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_volume=100,
                put_volume=120,
            ),
        )
    )

    metric = calculate_volume_pcr(snapshot=snapshot)

    assert metric.metric_name == "PCR_VOLUME"
    assert metric.value == 1.2
    assert metric.signal == "BULLISH"
    assert metric.status == "VALID"
    assert metric.sample_size == 4


@pytest.mark.parametrize(
    ("put_total", "call_total", "expected_signal"),
    (
        (120, 100, "BULLISH"),
        (110, 100, "BULLISH"),
        (100, 100, "NEUTRAL"),
        (95, 100, "NEUTRAL"),
        (90, 100, "BEARISH"),
        (80, 100, "BEARISH"),
    ),
)
def test_open_interest_pcr_signal_classification(
    put_total: int,
    call_total: int,
    expected_signal: str,
) -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=call_total,
                put_oi=put_total,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.signal == expected_signal


@pytest.mark.parametrize(
    ("put_total", "call_total", "expected_signal"),
    (
        (120, 100, "BULLISH"),
        (110, 100, "BULLISH"),
        (100, 100, "NEUTRAL"),
        (95, 100, "NEUTRAL"),
        (90, 100, "BEARISH"),
        (80, 100, "BEARISH"),
    ),
)
def test_volume_pcr_signal_classification(
    put_total: int,
    call_total: int,
    expected_signal: str,
) -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_volume=call_total,
                put_volume=put_total,
            ),
        )
    )

    metric = calculate_volume_pcr(snapshot=snapshot)

    assert metric.signal == expected_signal


@pytest.mark.parametrize(
    ("ratio", "expected_status", "expected_signal"),
    (
        (1.50, "VALID_WITH_WARNINGS", "BULLISH"),
        (1.60, "VALID_WITH_WARNINGS", "BULLISH"),
        (0.60, "VALID_WITH_WARNINGS", "BEARISH"),
        (0.50, "VALID_WITH_WARNINGS", "BEARISH"),
    ),
)
def test_open_interest_extreme_pcr_warns(
    ratio: float,
    expected_status: str,
    expected_signal: str,
) -> None:
    call_total = 100
    put_total = int(ratio * call_total)

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=call_total,
                put_oi=put_total,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.status == expected_status
    assert metric.signal == expected_signal
    assert metric.warnings


@pytest.mark.parametrize(
    ("ratio", "expected_status", "expected_signal"),
    (
        (1.50, "VALID_WITH_WARNINGS", "BULLISH"),
        (1.60, "VALID_WITH_WARNINGS", "BULLISH"),
        (0.60, "VALID_WITH_WARNINGS", "BEARISH"),
        (0.50, "VALID_WITH_WARNINGS", "BEARISH"),
    ),
)
def test_volume_extreme_pcr_warns(
    ratio: float,
    expected_status: str,
    expected_signal: str,
) -> None:
    call_total = 100
    put_total = int(ratio * call_total)

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_volume=call_total,
                put_volume=put_total,
            ),
        )
    )

    metric = calculate_volume_pcr(snapshot=snapshot)

    assert metric.status == expected_status
    assert metric.signal == expected_signal
    assert metric.warnings


def test_exact_bullish_threshold_is_bullish() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=110,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.value == 1.1
    assert metric.signal == "BULLISH"


def test_exact_bearish_threshold_is_bearish() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=90,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.value == 0.9
    assert metric.signal == "BEARISH"


def test_exact_extreme_high_threshold_warns() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=150,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.value == 1.5
    assert metric.status == "VALID_WITH_WARNINGS"


def test_exact_extreme_low_threshold_warns() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=60,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.value == 0.6
    assert metric.status == "VALID_WITH_WARNINGS"


def test_zero_call_open_interest_returns_unavailable() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=0,
                put_oi=100,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.value is None
    assert metric.signal == "UNAVAILABLE"
    assert metric.status == "UNAVAILABLE"
    assert metric.blockers == (
        "call_open_interest total is zero or unavailable",
    )


def test_zero_call_volume_returns_unavailable() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_volume=0,
                put_volume=100,
            ),
        )
    )

    metric = calculate_volume_pcr(snapshot=snapshot)

    assert metric.value is None
    assert metric.signal == "UNAVAILABLE"
    assert metric.status == "UNAVAILABLE"
    assert metric.blockers == (
        "call_volume total is zero or unavailable",
    )


def test_missing_call_open_interest_returns_unavailable() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=None,
                put_oi=100,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 1


def test_missing_call_volume_returns_unavailable() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_volume=None,
                put_volume=100,
            ),
        )
    )

    metric = calculate_volume_pcr(snapshot=snapshot)

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 1


def test_zero_put_open_interest_is_valid_bearish_extreme() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=0,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.value == 0.0
    assert metric.signal == "BEARISH"
    assert metric.status == "VALID_WITH_WARNINGS"


def test_zero_put_volume_is_valid_bearish_extreme() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_volume=100,
                put_volume=0,
            ),
        )
    )

    metric = calculate_volume_pcr(snapshot=snapshot)

    assert metric.value == 0.0
    assert metric.signal == "BEARISH"
    assert metric.status == "VALID_WITH_WARNINGS"


def test_missing_put_open_interest_contributes_no_value() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=100,
                put_oi=None,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=100,
                put_oi=100,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.value == 0.5
    assert metric.sample_size == 3


def test_missing_put_volume_contributes_no_value() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_volume=100,
                put_volume=None,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_volume=100,
                put_volume=100,
            ),
        )
    )

    metric = calculate_volume_pcr(snapshot=snapshot)

    assert metric.value == 0.5
    assert metric.sample_size == 3


def test_call_only_row_supported() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                include_put=False,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.value == 0.0
    assert metric.sample_size == 1


def test_put_only_row_has_unavailable_denominator() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                put_oi=100,
                include_call=False,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 1


def test_empty_chain_returns_unavailable_oi_pcr() -> None:
    metric = calculate_open_interest_pcr(
        snapshot=make_snapshot(())
    )

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 0
    assert metric.supporting_strikes == ()


def test_empty_chain_returns_unavailable_volume_pcr() -> None:
    metric = calculate_volume_pcr(
        snapshot=make_snapshot(())
    )

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 0
    assert metric.supporting_strikes == ()


def test_supporting_strikes_include_used_rows_only_for_oi() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=None,
                put_oi=None,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=100,
                put_oi=120,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.supporting_strikes == (22000.0,)


def test_supporting_strikes_include_used_rows_only_for_volume() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_volume=None,
                put_volume=None,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_volume=100,
                put_volume=120,
            ),
        )
    )

    metric = calculate_volume_pcr(snapshot=snapshot)

    assert metric.supporting_strikes == (22000.0,)


def test_supporting_strikes_remain_sorted() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.supporting_strikes == (
        21900.0,
        22000.0,
        22100.0,
    )


def test_open_interest_parameters_reconcile() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=200,
                put_oi=300,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )
    parameters = dict(metric.parameters)

    assert parameters["put_total"] == 300
    assert parameters["call_total"] == 200
    assert parameters["bullish_threshold"] == 1.1
    assert parameters["bearish_threshold"] == 0.9
    assert parameters["extreme_high_threshold"] == 1.5
    assert parameters["extreme_low_threshold"] == 0.6


def test_volume_parameters_reconcile() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_volume=200,
                put_volume=300,
            ),
        )
    )

    metric = calculate_volume_pcr(snapshot=snapshot)
    parameters = dict(metric.parameters)

    assert parameters["put_total"] == 300
    assert parameters["call_total"] == 200


def test_custom_policy_thresholds_are_used() -> None:
    policy = make_policy(
        pcr_bullish_threshold=1.20,
        pcr_bearish_threshold=0.80,
        pcr_extreme_high_threshold=1.60,
        pcr_extreme_low_threshold=0.50,
    )

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=110,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot,
        policy=policy,
    )

    assert metric.value == 1.1
    assert metric.signal == "NEUTRAL"


def test_custom_extreme_thresholds_are_used() -> None:
    policy = make_policy(
        pcr_bullish_threshold=1.10,
        pcr_bearish_threshold=0.90,
        pcr_extreme_high_threshold=2.00,
        pcr_extreme_low_threshold=0.40,
    )

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=150,
            ),
        )
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot,
        policy=policy,
    )

    assert metric.signal == "BULLISH"
    assert metric.status == "VALID"


def test_combined_api_returns_canonical_order() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=120,
                call_volume=200,
                put_volume=220,
            ),
        )
    )

    metrics = calculate_pcr_metrics(snapshot=snapshot)

    assert tuple(
        metric.metric_name
        for metric in metrics
    ) == (
        "PCR_OPEN_INTEREST",
        "PCR_VOLUME",
    )


def test_combined_api_matches_individual_results() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=120,
                call_volume=200,
                put_volume=220,
            ),
        )
    )

    combined = calculate_pcr_metrics(snapshot=snapshot)

    assert combined[0] == calculate_open_interest_pcr(
        snapshot=snapshot
    )
    assert combined[1] == calculate_volume_pcr(
        snapshot=snapshot
    )


def test_combined_api_uses_supplied_policy() -> None:
    policy = make_policy(
        pcr_bullish_threshold=1.20,
        pcr_bearish_threshold=0.80,
        pcr_extreme_high_threshold=1.60,
        pcr_extreme_low_threshold=0.50,
    )

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=110,
                call_volume=100,
                put_volume=110,
            ),
        )
    )

    oi_metric, volume_metric = calculate_pcr_metrics(
        snapshot=snapshot,
        policy=policy,
    )

    assert oi_metric.signal == "NEUTRAL"
    assert volume_metric.signal == "NEUTRAL"


@pytest.mark.parametrize(
    "function",
    (
        calculate_open_interest_pcr,
        calculate_volume_pcr,
        calculate_pcr_metrics,
    ),
)
def test_snapshot_type_validation(function) -> None:
    with pytest.raises(TypeError):
        function(snapshot="snapshot")


@pytest.mark.parametrize(
    "function",
    (
        calculate_open_interest_pcr,
        calculate_volume_pcr,
        calculate_pcr_metrics,
    ),
)
def test_policy_type_validation(function) -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
            ),
        )
    )

    with pytest.raises(TypeError):
        function(
            snapshot=snapshot,
            policy="policy",
        )


def test_snapshot_is_not_mutated() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=120,
            ),
        )
    )

    before = snapshot.to_dict()

    calculate_pcr_metrics(snapshot=snapshot)

    assert snapshot.to_dict() == before


def test_pcr_does_not_change_quote_values() -> None:
    row = make_row(
        row_id="row-1",
        strike=22000.0,
        call_oi=100,
        put_oi=120,
        call_volume=200,
        put_volume=240,
    )
    snapshot = make_snapshot((row,))

    calculate_pcr_metrics(snapshot=snapshot)

    assert row.call is not None
    assert row.put is not None
    assert row.call.open_interest == 100
    assert row.put.open_interest == 120
    assert row.call.volume == 200
    assert row.put.volume == 240


@pytest.mark.parametrize(
    ("symbol", "exchange"),
    (
        ("NIFTY", "NSE"),
        ("BANKNIFTY", "NSE"),
        ("FINNIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ),
)
def test_pcr_is_market_neutral(
    symbol: str,
    exchange: str,
) -> None:
    row = make_row(
        row_id="row-1",
        strike=22000.0,
        call_oi=100,
        put_oi=120,
    )

    snapshot = OptionChainSnapshotV1(
        option_chain_snapshot_id="snapshot-1",
        created_at=CREATED_AT,
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        underlying_value=22000.0,
        strike_rows=(
            OptionStrikeRowV1(
                strike_row_id=row.strike_row_id,
                underlying_symbol=symbol,
                exchange=exchange,
                expiry=EXPIRY,
                strike=row.strike,
                call=OptionQuoteV1(
                    **{
                        **row.call.to_dict(),
                        "option_quote_id": "call",
                        "created_at": CREATED_AT,
                        "expiry": EXPIRY,
                        "underlying_symbol": symbol,
                        "exchange": exchange,
                        "source_timestamp": CREATED_AT,
                        "blockers": (),
                        "warnings": (),
                    }
                ),
                put=OptionQuoteV1(
                    **{
                        **row.put.to_dict(),
                        "option_quote_id": "put",
                        "created_at": CREATED_AT,
                        "expiry": EXPIRY,
                        "underlying_symbol": symbol,
                        "exchange": exchange,
                        "source_timestamp": CREATED_AT,
                        "blockers": (),
                        "warnings": (),
                    }
                ),
                blockers=(),
                warnings=(),
            ),
        ),
        strike_count=1,
        complete_pair_count=1,
        call_only_count=0,
        put_only_count=0,
        minimum_strike=22000.0,
        maximum_strike=22000.0,
        source_timestamp=CREATED_AT,
        provider_name="TEST",
        blockers=(),
        warnings=(),
        execution_mode="PAPER",
        live_execution_eligible=False,
    )

    metric = calculate_open_interest_pcr(
        snapshot=snapshot
    )

    assert metric.value == 1.2
    assert metric.signal == "BULLISH"
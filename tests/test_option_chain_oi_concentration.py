"""Tests for deterministic option-chain OI concentration intelligence."""

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
from services.option_chain_intelligence.oi_concentration import (
    OI_CONCENTRATION_METRIC_NAME,
    calculate_oi_concentration,
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
    open_interest: int | None,
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
                open_interest=call_oi,
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
                open_interest=put_oi,
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
        underlying_symbol=symbol,
        exchange=exchange,
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


def test_metric_name_constant() -> None:
    assert OI_CONCENTRATION_METRIC_NAME == "OI_CONCENTRATION"


def test_basic_concentration_calculation() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=100,
                put_oi=100,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=300,
                put_oi=300,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_oi=100,
                put_oi=100,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.value == 0.6
    assert metric.signal == "CONCENTRATED"
    assert metric.status == "VALID"
    assert metric.sample_size == 6
    assert metric.supporting_strikes == (22000.0,)


@pytest.mark.parametrize(
    (
        "strike_totals",
        "expected_ratio",
        "expected_signal",
    ),
    (
        (
            (700, 100, 100, 100),
            0.70,
            "CONCENTRATED",
        ),
        (
            (350, 250, 200, 200),
            0.35,
            "CONCENTRATED",
        ),
        (
            (300, 250, 250, 200),
            0.30,
            "BALANCED",
        ),
        (
            (200, 200, 200, 200, 200),
            0.20,
            "BALANCED",
        ),
        (
            (
                150,
                150,
                140,
                140,
                140,
                140,
                140,
            ),
            0.15,
            "DISPERSED",
        ),
        (
            (
                100,
                100,
                100,
                100,
                100,
                100,
                100,
                100,
                100,
                100,
            ),
            0.10,
            "DISPERSED",
        ),
    ),
)
def test_concentration_signal_classification(
    strike_totals: tuple[int, ...],
    expected_ratio: float,
    expected_signal: str,
) -> None:
    rows = tuple(
        make_row(
            row_id=f"row-{index}",
            strike=21800.0 + index * 100.0,
            call_oi=strike_total // 2,
            put_oi=strike_total - strike_total // 2,
        )
        for index, strike_total in enumerate(
            strike_totals,
            start=1,
        )
    )

    metric = calculate_oi_concentration(
        snapshot=make_snapshot(rows)
    )

    assert metric.value == pytest.approx(expected_ratio)
    assert metric.signal == expected_signal


def test_exact_high_threshold_is_concentrated() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=175,
                put_oi=175,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=325,
                put_oi=325,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.value == 0.65
    assert metric.signal == "CONCENTRATED"


def test_exact_low_threshold_is_dispersed() -> None:
    snapshot = make_snapshot(
        tuple(
            make_row(
                row_id=f"row-{index}",
                strike=21800.0 + index * 100.0,
                call_oi=50,
                put_oi=50,
            )
            for index in range(7)
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.value == pytest.approx(1 / 7)
    assert metric.signal == "DISPERSED"


def test_multiple_dominant_strikes_warn() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=200,
                put_oi=200,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=200,
                put_oi=200,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_oi=100,
                put_oi=100,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.status == "VALID_WITH_WARNINGS"
    assert metric.supporting_strikes == (
        21900.0,
        22000.0,
    )
    assert metric.warnings == (
        "multiple strikes share the maximum combined open interest",
    )


def test_single_dominant_strike_has_no_warning() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=100,
                put_oi=100,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=300,
                put_oi=300,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.status == "VALID"
    assert metric.warnings == ()


def test_zero_total_open_interest_is_unavailable() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=0,
                put_oi=0,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.value is None
    assert metric.signal == "UNAVAILABLE"
    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 2
    assert metric.blockers == (
        "total chain open interest is zero or unavailable",
    )


def test_all_missing_open_interest_is_unavailable() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=None,
                put_oi=None,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 0
    assert metric.supporting_strikes == ()


def test_empty_chain_is_unavailable() -> None:
    metric = calculate_oi_concentration(
        snapshot=make_snapshot(())
    )

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 0
    assert metric.supporting_strikes == ()


def test_missing_call_oi_uses_put_only() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=None,
                put_oi=300,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=100,
                put_oi=100,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.value == 0.6
    assert metric.sample_size == 3
    assert metric.supporting_strikes == (21900.0,)


def test_missing_put_oi_uses_call_only() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=300,
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

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.value == 0.6
    assert metric.sample_size == 3
    assert metric.supporting_strikes == (21900.0,)


def test_call_only_row_supported() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=300,
                include_put=False,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.value == 1.0
    assert metric.signal == "CONCENTRATED"
    assert metric.sample_size == 1


def test_put_only_row_supported() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                put_oi=300,
                include_call=False,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.value == 1.0
    assert metric.signal == "CONCENTRATED"
    assert metric.sample_size == 1


def test_zero_oi_observation_is_counted() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=0,
                put_oi=100,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=100,
                put_oi=100,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.sample_size == 4
    assert metric.value == pytest.approx(2 / 3)


def test_parameters_reconcile() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=100,
                put_oi=100,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=300,
                put_oi=300,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )
    parameters = dict(metric.parameters)

    assert parameters["total_open_interest"] == 800
    assert parameters["maximum_strike_open_interest"] == 600
    assert parameters["high_ratio"] == 0.35
    assert parameters["low_ratio"] == 0.15
    assert parameters["dominant_strike_count"] == 1


def test_unavailable_parameters_include_thresholds() -> None:
    metric = calculate_oi_concentration(
        snapshot=make_snapshot(())
    )
    parameters = dict(metric.parameters)

    assert parameters["high_ratio"] == 0.35
    assert parameters["low_ratio"] == 0.15


def test_custom_policy_thresholds_are_used() -> None:
    policy = make_policy(
        oi_concentration_high_ratio=0.80,
        oi_concentration_low_ratio=0.20,
    )

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=300,
                put_oi=300,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=200,
                put_oi=200,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot,
        policy=policy,
    )

    assert metric.value == 0.6
    assert metric.signal == "BALANCED"


def test_custom_low_threshold_is_used() -> None:
    policy = make_policy(
        oi_concentration_high_ratio=0.60,
        oi_concentration_low_ratio=0.30,
    )

    snapshot = make_snapshot(
        tuple(
            make_row(
                row_id=f"row-{index}",
                strike=21800.0 + index * 100.0,
                call_oi=50,
                put_oi=50,
            )
            for index in range(4)
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot,
        policy=policy,
    )

    assert metric.value == 0.25
    assert metric.signal == "DISPERSED"


def test_supporting_strikes_are_sorted() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=200,
                put_oi=200,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=100,
                put_oi=100,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_oi=200,
                put_oi=200,
            ),
        )
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.supporting_strikes == (
        21900.0,
        22100.0,
    )


def test_snapshot_type_validation() -> None:
    with pytest.raises(TypeError):
        calculate_oi_concentration(
            snapshot="snapshot"
        )


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
        calculate_oi_concentration(
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
                put_oi=200,
            ),
        )
    )

    before = snapshot.to_dict()

    calculate_oi_concentration(snapshot=snapshot)

    assert snapshot.to_dict() == before


def test_quote_values_are_not_mutated() -> None:
    row = make_row(
        row_id="row-1",
        strike=22000.0,
        call_oi=100,
        put_oi=200,
    )
    snapshot = make_snapshot((row,))

    calculate_oi_concentration(snapshot=snapshot)

    assert row.call is not None
    assert row.put is not None
    assert row.call.open_interest == 100
    assert row.put.open_interest == 200


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
            strike=21900.0,
            call_oi=100,
            put_oi=100,
            symbol=symbol,
            exchange=exchange,
        ),
        make_row(
            row_id="row-2",
            strike=22000.0,
            call_oi=300,
            put_oi=300,
            symbol=symbol,
            exchange=exchange,
        ),
    )

    snapshot = make_snapshot(
        rows,
        symbol=symbol,
        exchange=exchange,
    )

    metric = calculate_oi_concentration(
        snapshot=snapshot
    )

    assert metric.value == 0.75
    assert metric.signal == "CONCENTRATED"


def test_no_directional_buy_sell_output() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=300,
                put_oi=300,
            ),
        )
    )

    serialized = calculate_oi_concentration(
        snapshot=snapshot
    ).to_dict()

    assert "action" not in serialized
    assert "decision" not in serialized
    assert "option_selection" not in serialized
    assert "risk" not in serialized
    assert "execution" not in serialized
"""Tests for deterministic option-chain OI buildup intelligence."""

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
from services.option_chain_intelligence.oi_buildup import (
    OI_BUILDUP_METRIC_NAME,
    calculate_oi_buildup,
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
    change_in_open_interest: int | None,
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
        change_in_open_interest=change_in_open_interest,
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
    call_change: int | None = 10,
    put_change: int | None = 10,
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
                change_in_open_interest=call_change,
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
                change_in_open_interest=put_change,
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
    assert OI_BUILDUP_METRIC_NAME == "OI_BUILDUP"


def test_basic_bullish_buildup() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_change=20,
                put_change=50,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_change=30,
                put_change=70,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.value == pytest.approx(70 / 170)
    assert metric.signal == "BULLISH"
    assert metric.status == "VALID"
    assert metric.sample_size == 4


def test_basic_bearish_buildup() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_change=80,
                put_change=20,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_change=40,
                put_change=10,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.value == pytest.approx(-90 / 150)
    assert metric.signal == "BEARISH"
    assert metric.status == "VALID"


def test_equal_changes_are_neutral() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=50,
                put_change=50,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.value == 0.0
    assert metric.signal == "NEUTRAL"


def test_zero_gross_change_is_neutral() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=0,
                put_change=0,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.value == 0.0
    assert metric.signal == "NEUTRAL"
    assert metric.sample_size == 2


def test_all_missing_changes_are_unavailable() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=None,
                put_change=None,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.value is None
    assert metric.signal == "UNAVAILABLE"
    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 0
    assert metric.blockers == (
        "change in open interest is unavailable for all quotes",
    )


def test_empty_chain_is_unavailable() -> None:
    metric = calculate_oi_buildup(
        snapshot=make_snapshot(())
    )

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 0


def test_missing_call_change_uses_put_change() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=None,
                put_change=50,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.value == 1.0
    assert metric.signal == "BULLISH"
    assert metric.sample_size == 1


def test_missing_put_change_uses_call_change() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=50,
                put_change=None,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.value == -1.0
    assert metric.signal == "BEARISH"
    assert metric.sample_size == 1


def test_call_only_row_supported() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=40,
                include_put=False,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.value == -1.0
    assert metric.signal == "BEARISH"


def test_put_only_row_supported() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                put_change=40,
                include_call=False,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.value == 1.0
    assert metric.signal == "BULLISH"


def test_signed_negative_changes_are_preserved() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=-20,
                put_change=40,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)
    parameters = dict(metric.parameters)

    assert parameters["call_change_total"] == -20
    assert parameters["put_change_total"] == 40
    assert parameters["net_buildup"] == 60
    assert metric.value == 1.0
    assert metric.signal == "BULLISH"


def test_both_sides_unwinding_warns() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=-50,
                put_change=-20,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.status == "VALID_WITH_WARNINGS"
    assert metric.warnings == (
        "aggregate CALL and PUT open interest are both unwinding",
    )


def test_one_side_unwinding_does_not_trigger_warning() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=-20,
                put_change=40,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.status == "VALID"
    assert metric.warnings == ()


@pytest.mark.parametrize(
    ("call_change", "put_change", "expected_signal"),
    (
        (10, 20, "BULLISH"),
        (20, 10, "BEARISH"),
        (10, 10, "NEUTRAL"),
        (-10, 10, "BULLISH"),
        (10, -10, "BEARISH"),
        (-10, -10, "NEUTRAL"),
    ),
)
def test_signal_classification(
    call_change: int,
    put_change: int,
    expected_signal: str,
) -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=call_change,
                put_change=put_change,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.signal == expected_signal


def test_minimum_change_threshold_can_force_neutral() -> None:
    policy = make_policy(
        oi_buildup_minimum_absolute_change=10
    )

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=10,
                put_change=15,
            ),
        )
    )

    metric = calculate_oi_buildup(
        snapshot=snapshot,
        policy=policy,
    )

    assert dict(metric.parameters)["net_buildup"] == 5
    assert metric.signal == "NEUTRAL"


def test_exact_minimum_change_is_directional() -> None:
    policy = make_policy(
        oi_buildup_minimum_absolute_change=10
    )

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=10,
                put_change=20,
            ),
        )
    )

    metric = calculate_oi_buildup(
        snapshot=snapshot,
        policy=policy,
    )

    assert dict(metric.parameters)["net_buildup"] == 10
    assert metric.signal == "BULLISH"


def test_parameters_reconcile() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_change=20,
                put_change=50,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_change=30,
                put_change=70,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)
    parameters = dict(metric.parameters)

    assert parameters["put_change_total"] == 120
    assert parameters["call_change_total"] == 50
    assert parameters["net_buildup"] == 70
    assert parameters["gross_absolute_change"] == 170
    assert parameters["minimum_absolute_change"] == 1


def test_supporting_strikes_include_used_rows_only() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_change=None,
                put_change=None,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_change=10,
                put_change=20,
            ),
        )
    )

    metric = calculate_oi_buildup(snapshot=snapshot)

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

    metric = calculate_oi_buildup(snapshot=snapshot)

    assert metric.supporting_strikes == (
        21900.0,
        22000.0,
        22100.0,
    )


def test_snapshot_type_validation() -> None:
    with pytest.raises(TypeError):
        calculate_oi_buildup(snapshot="snapshot")


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
        calculate_oi_buildup(
            snapshot=snapshot,
            policy="policy",
        )


def test_snapshot_is_not_mutated() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=10,
                put_change=20,
            ),
        )
    )

    before = snapshot.to_dict()

    calculate_oi_buildup(snapshot=snapshot)

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
            call_change=10,
            put_change=20,
            symbol=symbol,
            exchange=exchange,
        ),
    )

    metric = calculate_oi_buildup(
        snapshot=make_snapshot(
            rows,
            symbol=symbol,
            exchange=exchange,
        )
    )

    assert metric.value == pytest.approx(1 / 3)
    assert metric.signal == "BULLISH"


def test_no_decision_or_execution_output() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_change=10,
                put_change=20,
            ),
        )
    )

    serialized = calculate_oi_buildup(
        snapshot=snapshot
    ).to_dict()

    assert "action" not in serialized
    assert "decision" not in serialized
    assert "ranking" not in serialized
    assert "risk" not in serialized
    assert "execution" not in serialized
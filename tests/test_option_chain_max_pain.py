"""Tests for deterministic option-chain max-pain intelligence."""

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
from services.option_chain_intelligence.max_pain import (
    MAX_PAIN_METRIC_NAME,
    calculate_max_pain,
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
    underlying_value: float | None = 22000.0,
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
        underlying_value=underlying_value,
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
    underlying_value: float | None = 22000.0,
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
                underlying_value=underlying_value,
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
                underlying_value=underlying_value,
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
    underlying_value: float | None = 22000.0,
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
        underlying_value=underlying_value,
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
    assert MAX_PAIN_METRIC_NAME == "MAX_PAIN"


def test_basic_max_pain_calculation() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=100,
                put_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=500,
                put_oi=500,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_oi=500,
                put_oi=100,
            ),
        )
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.value == 22000.0
    assert metric.signal == "NEUTRAL"
    assert metric.status == "VALID"
    assert metric.sample_size == 6
    assert metric.supporting_strikes == (22000.0,)

    parameters = dict(metric.parameters)

    assert parameters["minimum_total_pain"] == 20000.0
    assert parameters["total_open_interest"] == 2200
    assert parameters["signed_distance_bps"] == 0.0
    assert parameters["absolute_distance_bps"] == 0.0
    assert parameters["tied_minimum_count"] == 1


def test_max_pain_above_underlying_is_bullish() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=50,
                put_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=22200.0,
                call_oi=500,
                put_oi=500,
            ),
            make_row(
                row_id="row-3",
                strike=22400.0,
                call_oi=500,
                put_oi=50,
            ),
        ),
        underlying_value=22000.0,
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.value == 22200.0
    assert metric.signal == "BULLISH"
    assert metric.status == "VALID"


def test_max_pain_below_underlying_is_bearish() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21600.0,
                call_oi=50,
                put_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=21800.0,
                call_oi=500,
                put_oi=500,
            ),
            make_row(
                row_id="row-3",
                strike=22000.0,
                call_oi=500,
                put_oi=50,
            ),
        ),
        underlying_value=22000.0,
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.value == 21800.0
    assert metric.signal == "BEARISH"
    assert metric.status == "VALID"


def test_near_distance_is_neutral() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21950.0,
                call_oi=100,
                put_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=500,
                put_oi=500,
            ),
            make_row(
                row_id="row-3",
                strike=22050.0,
                call_oi=500,
                put_oi=100,
            ),
        ),
        underlying_value=22000.0,
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.value == 22000.0
    assert metric.signal == "NEUTRAL"


def test_far_distance_warns() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=10,
                put_oi=1000,
            ),
            make_row(
                row_id="row-2",
                strike=22500.0,
                call_oi=1000,
                put_oi=1000,
            ),
            make_row(
                row_id="row-3",
                strike=23000.0,
                call_oi=1000,
                put_oi=10,
            ),
        ),
        underlying_value=22000.0,
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.value == 22500.0
    assert metric.signal == "BULLISH"
    assert metric.status == "VALID_WITH_WARNINGS"
    assert (
        "max-pain strike is far from the current underlying value"
        in metric.warnings
    )


def test_exact_far_threshold_warns() -> None:
    policy = make_policy(
        max_pain_near_distance_bps=50.0,
        max_pain_far_distance_bps=200.0,
    )

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=10,
                put_oi=1000,
            ),
            make_row(
                row_id="row-2",
                strike=22440.0,
                call_oi=1000,
                put_oi=1000,
            ),
            make_row(
                row_id="row-3",
                strike=22880.0,
                call_oi=1000,
                put_oi=10,
            ),
        ),
        underlying_value=22000.0,
    )

    metric = calculate_max_pain(
        snapshot=snapshot,
        policy=policy,
    )

    assert metric.value == 22440.0
    assert dict(metric.parameters)["absolute_distance_bps"] == 200.0
    assert metric.status == "VALID_WITH_WARNINGS"


def test_missing_underlying_value_is_unavailable() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
            ),
        ),
        underlying_value=None,
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.value is None
    assert metric.signal == "UNAVAILABLE"
    assert metric.status == "UNAVAILABLE"
    assert metric.blockers == (
        "underlying value is unavailable",
    )


def test_empty_chain_is_unavailable() -> None:
    metric = calculate_max_pain(
        snapshot=make_snapshot(())
    )

    assert metric.status == "UNAVAILABLE"
    assert metric.blockers == (
        "option chain contains no candidate strikes",
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

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 0
    assert metric.blockers == (
        "open interest is unavailable for all option quotes",
    )


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

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 2
    assert metric.blockers == (
        "total option-chain open interest is zero",
    )


def test_call_only_rows_are_supported() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=100,
                include_put=False,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=500,
                include_put=False,
            ),
        )
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.status in {"VALID", "VALID_WITH_WARNINGS"}
    assert metric.sample_size == 2


def test_put_only_rows_are_supported() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                put_oi=500,
                include_call=False,
            ),
            make_row(
                row_id="row-2",
                strike=22100.0,
                put_oi=100,
                include_call=False,
            ),
        )
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.status in {"VALID", "VALID_WITH_WARNINGS"}
    assert metric.sample_size == 2


def test_missing_side_open_interest_is_ignored() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=None,
                put_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=500,
                put_oi=None,
            ),
        )
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.sample_size == 2
    assert metric.status in {"VALID", "VALID_WITH_WARNINGS"}


def test_tied_minimum_selects_nearest_underlying() -> None:
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
                call_oi=100,
                put_oi=100,
            ),
        ),
        underlying_value=21980.0,
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.value == 22000.0
    assert metric.supporting_strikes == (
        21900.0,
        22000.0,
    )
    assert metric.status == "VALID_WITH_WARNINGS"
    assert (
        "multiple strikes share the minimum aggregate option payout"
        in metric.warnings
    )


def test_tied_equal_distance_selects_lower_strike() -> None:
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
                strike=22100.0,
                call_oi=100,
                put_oi=100,
            ),
        ),
        underlying_value=22000.0,
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.value == 21900.0
    assert metric.supporting_strikes == (
        21900.0,
        22100.0,
    )


def test_supporting_strikes_are_sorted() -> None:
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
                call_oi=100,
                put_oi=100,
            ),
        )
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.supporting_strikes == tuple(
        sorted(metric.supporting_strikes)
    )


def test_parameters_reconcile() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=100,
                put_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=500,
                put_oi=500,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_oi=500,
                put_oi=100,
            ),
        )
    )

    parameters = dict(
        calculate_max_pain(snapshot=snapshot).parameters
    )

    assert parameters["underlying_value"] == 22000.0
    assert parameters["minimum_total_pain"] == 20000.0
    assert parameters["near_distance_bps"] == 50.0
    assert parameters["far_distance_bps"] == 200.0
    assert parameters["tied_minimum_count"] == 1
    assert parameters["total_open_interest"] == 2200


def test_custom_distance_thresholds_are_used() -> None:
    policy = make_policy(
        max_pain_near_distance_bps=100.0,
        max_pain_far_distance_bps=300.0,
    )

    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=10,
                put_oi=1000,
            ),
            make_row(
                row_id="row-2",
                strike=22200.0,
                call_oi=1000,
                put_oi=1000,
            ),
            make_row(
                row_id="row-3",
                strike=22400.0,
                call_oi=1000,
                put_oi=10,
            ),
        )
    )

    metric = calculate_max_pain(
        snapshot=snapshot,
        policy=policy,
    )

    assert metric.value == 22200.0
    assert metric.signal == "NEUTRAL"
    assert metric.status == "VALID"


def test_snapshot_type_validation() -> None:
    with pytest.raises(TypeError):
        calculate_max_pain(snapshot="snapshot")


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
        calculate_max_pain(
            snapshot=snapshot,
            policy="policy",
        )


def test_snapshot_is_not_mutated() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=100,
                put_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=500,
                put_oi=500,
            ),
        )
    )

    before = snapshot.to_dict()

    calculate_max_pain(snapshot=snapshot)

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
            strike=21900.0,
            call_oi=100,
            put_oi=500,
            symbol=symbol,
            exchange=exchange,
        ),
        make_row(
            row_id="row-2",
            strike=22000.0,
            call_oi=500,
            put_oi=500,
            symbol=symbol,
            exchange=exchange,
        ),
        make_row(
            row_id="row-3",
            strike=22100.0,
            call_oi=500,
            put_oi=100,
            symbol=symbol,
            exchange=exchange,
        ),
    )

    snapshot = make_snapshot(
        rows,
        symbol=symbol,
        exchange=exchange,
    )

    metric = calculate_max_pain(snapshot=snapshot)

    assert metric.value == 22000.0
    assert metric.signal == "NEUTRAL"


def test_no_decision_or_execution_output() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=100,
                put_oi=100,
            ),
        )
    )

    serialized = calculate_max_pain(
        snapshot=snapshot
    ).to_dict()

    assert "action" not in serialized
    assert "decision" not in serialized
    assert "ranking" not in serialized
    assert "risk" not in serialized
    assert "execution" not in serialized
"""Behavioral coverage for canonical option-chain structural quality.

This suite deliberately constructs its inputs through the public normalizer.
It exercises only structural, freshness, and policy outcomes; it does not
assert or derive any option-chain intelligence.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from services.contracts import DEFAULT_OPTION_CHAIN_POLICY
from services.option_chain_intelligence import (
    evaluate_option_chain_quality,
    normalize_option_chain_records,
)


NOW = datetime(2025, 1, 2, 9, 30, tzinfo=timezone.utc)
EXPIRY = date(2025, 1, 30)
IDENTITIES = (
    ("NIFTY", "NSE"),
    ("BANKNIFTY", "NSE"),
    ("FINNIFTY", "NSE"),
    ("SENSEX", "BSE"),
)


def _record(
    *,
    strike: float,
    option_type: str,
    source_record_id: str,
    crossed: bool = False,
) -> dict[str, object]:
    return {
        "strike": strike,
        "option_type": option_type,
        "ltp": 10.0,
        "bid_price": 12.0 if crossed else 9.0,
        "ask_price": 11.0,
        "bid_quantity": 100,
        "ask_quantity": 110,
        "volume": 1_000,
        "open_interest": 2_000,
        "change_in_open_interest": 25,
        "implied_volatility": 15.0,
        "underlying_value": 20_000.0,
        "source_record_id": source_record_id,
        "is_complete": True,
    }


def _records_for_shape(
    *,
    complete_pairs: int = 10,
    call_only: int = 0,
    put_only: int = 0,
    crossed_sides: frozenset[tuple[int, str]] = frozenset(),
    duplicate_sides: tuple[tuple[int, str], ...] = (),
) -> tuple[dict[str, object], ...]:
    """Return canonical records with a deliberately irregular strike layout."""
    total = complete_pairs + call_only + put_only
    records: list[dict[str, object]] = []
    for index in range(total):
        strike = 100.0 + index * 37.5
        if index < complete_pairs:
            sides = ("CALL", "PUT")
        elif index < complete_pairs + call_only:
            sides = ("CALL",)
        else:
            sides = ("PUT",)
        for side in sides:
            records.append(
                _record(
                    strike=strike,
                    option_type=side,
                    source_record_id=f"{side}-{index}",
                    crossed=(index, side) in crossed_sides,
                )
            )
    for duplicate_number, (index, side) in enumerate(duplicate_sides, start=1):
        records.append(
            _record(
                strike=100.0 + index * 37.5,
                option_type=side,
                source_record_id=f"duplicate-{side}-{index}-{duplicate_number}",
                crossed=(index, side) in crossed_sides,
            )
        )
    # Provider-neutral input is unordered; normalizer ordering is what matters.
    return tuple(reversed(records))


def _snapshot(
    *,
    records: tuple[dict[str, object], ...] | None = None,
    source_timestamp: datetime = NOW,
    underlying_symbol: str = "NIFTY",
    exchange: str = "NSE",
):
    return normalize_option_chain_records(
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        expiry=EXPIRY,
        underlying_value=20_000.0,
        source_timestamp=source_timestamp,
        provider_name="QUALITY_TEST",
        records=_records_for_shape() if records is None else records,
        clock=lambda: NOW,
    )


def _policy(**changes):
    return replace(DEFAULT_OPTION_CHAIN_POLICY, **changes)


def _quality(snapshot, *, policy=None, clock=lambda: NOW, factory=None):
    return evaluate_option_chain_quality(
        snapshot=snapshot,
        policy=policy,
        clock=clock,
        option_chain_quality_result_id_factory=factory,
    )


def _snapshot_diagnostic(snapshot, *, marker: str, kind: str):
    values = snapshot.blockers if kind == "blocker" else snapshot.warnings
    return replace(snapshot, **{f"{kind}s": values + (marker,)})


def _row_diagnostic(snapshot, *, marker: str, kind: str):
    row = snapshot.strike_rows[0]
    values = row.blockers if kind == "blocker" else row.warnings
    changed = replace(row, **{f"{kind}s": values + (marker,)})
    return replace(snapshot, strike_rows=(changed,) + snapshot.strike_rows[1:])


def _quote_diagnostic(snapshot, *, marker: str, kind: str):
    row = snapshot.strike_rows[0]
    quote = row.call if row.call is not None else row.put
    assert quote is not None
    values = quote.blockers if kind == "blocker" else quote.warnings
    changed_quote = replace(quote, **{f"{kind}s": values + (marker,)})
    if row.call is quote:
        changed_row = replace(row, call=changed_quote)
    else:
        changed_row = replace(row, put=changed_quote)
    return replace(snapshot, strike_rows=(changed_row,) + snapshot.strike_rows[1:])


def _diagnosed(snapshot, *, layer: str, marker: str, kind: str):
    builders = {
        "snapshot": _snapshot_diagnostic,
        "row": _row_diagnostic,
        "quote": _quote_diagnostic,
    }
    return builders[layer](snapshot, marker=marker, kind=kind)


@pytest.mark.parametrize(
    "build,expected_status",
    (
        pytest.param(
            lambda: (
                _snapshot_diagnostic(
                    _snapshot(source_timestamp=NOW - timedelta(seconds=301)),
                    marker="upstream_failed",
                    kind="blocker",
                ),
                None,
            ),
            "FAILED",
            id="failed-precedes-stale",
        ),
        pytest.param(
            lambda: (
                _snapshot(
                    records=_records_for_shape(crossed_sides=frozenset({(0, "CALL")})),
                    source_timestamp=NOW + timedelta(seconds=6),
                ),
                None,
            ),
            "MALFORMED",
            id="malformed-precedes-future",
        ),
        pytest.param(
            lambda: (_snapshot(records=(), source_timestamp=NOW + timedelta(seconds=6)), None),
            "FUTURE",
            id="future-precedes-empty",
        ),
        pytest.param(
            lambda: (_snapshot(records=(), source_timestamp=NOW - timedelta(seconds=301)), None),
            "EMPTY",
            id="empty-precedes-stale",
        ),
        pytest.param(
            lambda: (
                _snapshot(
                    records=_records_for_shape(complete_pairs=4, call_only=6),
                    source_timestamp=NOW - timedelta(seconds=301),
                ),
                None,
            ),
            "STALE",
            id="stale-precedes-incomplete",
        ),
        pytest.param(
            lambda: (_snapshot(records=_records_for_shape(complete_pairs=4, call_only=6)), None),
            "INCOMPLETE",
            id="incomplete-precedes-warnings",
        ),
        pytest.param(
            lambda: (_snapshot_diagnostic(_snapshot(), marker="upstream_warning", kind="warning"), None),
            "VALID_WITH_WARNINGS",
            id="warnings-precede-valid",
        ),
        pytest.param(lambda: (_snapshot(), None), "VALID", id="valid-final-status"),
    ),
)
def test_status_precedence_is_deterministic_for_contract_valid_snapshots(build, expected_status):
    snapshot, policy = build()
    assert _quality(snapshot, policy=policy).quality_status == expected_status


@pytest.mark.parametrize(
    "source_timestamp,expected_status,expected_age",
    (
        (NOW, "VALID", 0.0),
        (NOW - timedelta(microseconds=1), "VALID", 0.000001),
        (NOW - timedelta(seconds=299, microseconds=999_999), "VALID", 299.999999),
        (NOW - timedelta(seconds=300), "VALID", 300.0),
        (NOW - timedelta(seconds=300, microseconds=1), "STALE", 300.000001),
        (NOW + timedelta(microseconds=1), "VALID", -0.000001),
        (NOW + timedelta(seconds=5), "VALID", -5.0),
        (NOW + timedelta(seconds=5, microseconds=1), "FUTURE", -5.000001),
        (NOW + timedelta(seconds=60), "FUTURE", -60.0),
    ),
)
def test_freshness_and_future_boundaries_use_strict_policy_tolerances(
    source_timestamp,
    expected_status,
    expected_age,
):
    result = _quality(_snapshot(source_timestamp=source_timestamp))
    assert result.quality_status == expected_status
    assert result.age_seconds == pytest.approx(expected_age)


@pytest.mark.parametrize(
    "complete_pairs,call_only,put_only,expected_status",
    (
        (10, 0, 0, "VALID"),
        (5, 5, 0, "VALID_WITH_WARNINGS"),
        (5, 0, 5, "VALID_WITH_WARNINGS"),
        (5, 3, 2, "VALID_WITH_WARNINGS"),
        (4, 3, 3, "INCOMPLETE"),
        (9, 0, 0, "INCOMPLETE"),
        (0, 10, 0, "INCOMPLETE"),
    ),
)
def test_quality_counts_and_ratio_reconcile_each_honest_missing_side_shape(
    complete_pairs,
    call_only,
    put_only,
    expected_status,
):
    snapshot = _snapshot(records=_records_for_shape(
        complete_pairs=complete_pairs,
        call_only=call_only,
        put_only=put_only,
    ))
    result = _quality(snapshot)
    total = complete_pairs + call_only + put_only
    assert result.quality_status == expected_status
    assert (result.total_strikes, result.complete_pair_count) == (total, complete_pairs)
    assert (result.missing_call_count, result.missing_put_count) == (put_only, call_only)
    assert result.completeness_ratio == pytest.approx(complete_pairs / total if total else 0.0)


@pytest.mark.parametrize(
    "records,policy_changes,expected_status,expected_diagnostic,diagnostic_location",
    (
        pytest.param(
            _records_for_shape(complete_pairs=9),
            {"incomplete_behavior": "BLOCK"},
            "INCOMPLETE",
            "minimum_total_strikes_not_met",
            "blockers",
            id="total-strikes-block",
        ),
        pytest.param(
            _records_for_shape(complete_pairs=9),
            {"incomplete_behavior": "WARN"},
            "VALID_WITH_WARNINGS",
            "minimum_total_strikes_not_met",
            "warnings",
            id="total-strikes-warn",
        ),
        pytest.param(
            _records_for_shape(complete_pairs=9),
            {"incomplete_behavior": "ALLOW"},
            "VALID",
            None,
            None,
            id="total-strikes-allow",
        ),
        pytest.param(
            _records_for_shape(complete_pairs=5, call_only=5),
            {"missing_side_behavior": "BLOCK"},
            "INCOMPLETE",
            "missing_put_side",
            "blockers",
            id="missing-side-block",
        ),
        pytest.param(
            _records_for_shape(complete_pairs=5, call_only=5),
            {"missing_side_behavior": "WARN"},
            "VALID_WITH_WARNINGS",
            "missing_put_side",
            "warnings",
            id="missing-side-warn",
        ),
        pytest.param(
            _records_for_shape(complete_pairs=5, call_only=5),
            {"missing_side_behavior": "ALLOW"},
            "VALID",
            None,
            None,
            id="missing-side-allow",
        ),
        pytest.param(
            _records_for_shape(complete_pairs=4, call_only=6),
            {"incomplete_behavior": "BLOCK", "missing_side_behavior": "ALLOW"},
            "INCOMPLETE",
            "minimum_complete_pairs_not_met",
            "blockers",
            id="complete-pairs-block",
        ),
        pytest.param(
            _records_for_shape(complete_pairs=4, call_only=6),
            {"incomplete_behavior": "WARN", "missing_side_behavior": "ALLOW"},
            "VALID_WITH_WARNINGS",
            "minimum_complete_pairs_not_met",
            "warnings",
            id="complete-pairs-warn",
        ),
        pytest.param(
            _records_for_shape(complete_pairs=4, call_only=6),
            {"incomplete_behavior": "ALLOW", "missing_side_behavior": "ALLOW"},
            "VALID",
            None,
            None,
            id="complete-pairs-allow",
        ),
        pytest.param(
            _records_for_shape(),
            {"minimum_total_strikes": 11},
            "INCOMPLETE",
            "minimum_total_strikes_not_met",
            "blockers",
            id="custom-total-threshold",
        ),
        pytest.param(
            _records_for_shape(),
            {"minimum_complete_pairs": 11},
            "INCOMPLETE",
            "minimum_complete_pairs_not_met",
            "blockers",
            id="custom-pair-threshold",
        ),
        pytest.param(
            _records_for_shape(complete_pairs=5, call_only=5),
            {"minimum_completeness_ratio": 0.75, "missing_side_behavior": "ALLOW"},
            "INCOMPLETE",
            "minimum_completeness_ratio_not_met",
            "blockers",
            id="custom-ratio-threshold",
        ),
        pytest.param(
            _records_for_shape(complete_pairs=5, call_only=5),
            {
                "minimum_total_strikes": 10,
                "minimum_complete_pairs": 5,
                "minimum_completeness_ratio": 0.5,
                "missing_side_behavior": "ALLOW",
            },
            "VALID",
            None,
            None,
            id="exact-thresholds-accepted",
        ),
    ),
)
def test_policy_threshold_and_missing_side_behaviors_are_explicit(
    records,
    policy_changes,
    expected_status,
    expected_diagnostic,
    diagnostic_location,
):
    result = _quality(_snapshot(records=records), policy=_policy(**policy_changes))
    assert result.quality_status == expected_status
    if expected_diagnostic is not None:
        assert expected_diagnostic in getattr(result, diagnostic_location)
    else:
        assert result.blockers == ()
        assert result.warnings == ()


@pytest.mark.parametrize(
    "behavior,expected_status,diagnostic_location",
    (
        ("BLOCK", "MALFORMED", "blockers"),
        ("WARN", "VALID_WITH_WARNINGS", "warnings"),
        ("ALLOW", "VALID", None),
    ),
)
def test_crossed_market_behavior_is_controlled_by_policy(behavior, expected_status, diagnostic_location):
    snapshot = _snapshot(records=_records_for_shape(crossed_sides=frozenset({(0, "CALL")})))
    result = _quality(snapshot, policy=_policy(crossed_market_behavior=behavior))
    assert result.quality_status == expected_status
    assert result.malformed_quote_count == 1
    if diagnostic_location is None:
        assert result.warnings == ()
    else:
        assert "crossed_market" in getattr(result, diagnostic_location)


@pytest.mark.parametrize(
    "behavior,expected_status,diagnostic_location",
    (
        ("BLOCK", "MALFORMED", "blockers"),
        ("WARN", "VALID_WITH_WARNINGS", "warnings"),
        ("ALLOW", "VALID", None),
    ),
)
def test_duplicate_side_behavior_is_controlled_by_policy(behavior, expected_status, diagnostic_location):
    snapshot = _snapshot(records=_records_for_shape(duplicate_sides=((0, "CALL"),)))
    result = _quality(snapshot, policy=_policy(duplicate_strike_behavior=behavior))
    assert result.quality_status == expected_status
    assert result.duplicate_strike_count == 1
    if diagnostic_location is None:
        assert result.warnings == ()
    else:
        assert "duplicate_option_side" in getattr(result, diagnostic_location)


@pytest.mark.parametrize(
    "crossed_behavior,duplicate_behavior",
    tuple(
        (crossed_behavior, duplicate_behavior)
        for crossed_behavior in ("BLOCK", "WARN", "ALLOW")
        for duplicate_behavior in ("BLOCK", "WARN", "ALLOW")
    ),
)
def test_crossed_and_duplicate_policy_interactions_preserve_block_over_warning_precedence(
    crossed_behavior,
    duplicate_behavior,
):
    snapshot = _snapshot(
        records=_records_for_shape(
            crossed_sides=frozenset({(0, "CALL")}),
            duplicate_sides=((1, "PUT"),),
        )
    )
    result = _quality(snapshot, policy=_policy(
        crossed_market_behavior=crossed_behavior,
        duplicate_strike_behavior=duplicate_behavior,
    ))
    if "BLOCK" in (crossed_behavior, duplicate_behavior):
        assert result.quality_status == "MALFORMED"
        if crossed_behavior == "BLOCK":
            assert "crossed_market" in result.blockers
        if duplicate_behavior == "BLOCK":
            assert "duplicate_option_side" in result.blockers
    elif "WARN" in (crossed_behavior, duplicate_behavior):
        assert result.quality_status == "VALID_WITH_WARNINGS"
        if crossed_behavior == "WARN":
            assert "crossed_market" in result.warnings
        if duplicate_behavior == "WARN":
            assert "duplicate_option_side" in result.warnings
    else:
        assert result.quality_status == "VALID"
        assert result.warnings == ()


@pytest.mark.parametrize(
    "layer,kind,marker,expected_status,expected_location",
    (
        ("snapshot", "warning", "upstream_warning", "VALID_WITH_WARNINGS", "warnings"),
        ("row", "warning", "row_warning", "VALID_WITH_WARNINGS", "warnings"),
        ("quote", "warning", "quote_warning", "VALID_WITH_WARNINGS", "warnings"),
        ("snapshot", "warning", "malformed_source", "MALFORMED", "warnings"),
        ("row", "warning", "malformed_row", "MALFORMED", "warnings"),
        ("quote", "warning", "malformed_quote", "MALFORMED", "warnings"),
        ("snapshot", "blocker", "snapshot_failed", "FAILED", "blockers"),
        ("row", "blocker", "row_failed", "FAILED", "blockers"),
        ("quote", "blocker", "quote_failed", "FAILED", "blockers"),
        ("snapshot", "blocker", "unclassified_source_blocker", "MALFORMED", "blockers"),
    ),
)
def test_snapshot_row_and_quote_diagnostics_are_observable_without_directional_interpretation(
    layer,
    kind,
    marker,
    expected_status,
    expected_location,
):
    snapshot = _diagnosed(_snapshot(), layer=layer, kind=kind, marker=marker)
    result = _quality(snapshot)
    assert result.quality_status == expected_status
    assert marker in getattr(result, expected_location)


@pytest.mark.parametrize(
    "crossed_sides,expected_count",
    (
        (frozenset({(0, "CALL")}), 1),
        (frozenset({(0, "CALL"), (0, "PUT")}), 2),
        (frozenset({(0, "CALL"), (0, "PUT"), (1, "CALL")}), 3),
    ),
)
def test_malformed_quote_count_tracks_each_explicit_crossed_quote(crossed_sides, expected_count):
    result = _quality(_snapshot(records=_records_for_shape(crossed_sides=crossed_sides)))
    assert result.quality_status == "MALFORMED"
    assert result.malformed_quote_count == expected_count


@pytest.mark.parametrize("duplicate_count", (1, 2, 3))
def test_duplicate_strike_count_tracks_each_ignored_duplicate_side(duplicate_count):
    duplicates = tuple((0, "CALL") for _ in range(duplicate_count))
    result = _quality(_snapshot(records=_records_for_shape(duplicate_sides=duplicates)))
    assert result.quality_status == "MALFORMED"
    assert result.duplicate_strike_count == duplicate_count


def test_quality_uses_its_clock_once_and_copies_the_shared_timestamp_to_created_at():
    calls: list[str] = []

    def clock():
        calls.append("clock")
        return NOW

    result = _quality(_snapshot(), clock=clock)
    assert calls == ["clock"]
    assert result.created_at == NOW


def test_quality_factory_is_called_once_after_validation_and_preserves_snapshot_linkage():
    calls: list[str] = []

    def factory():
        calls.append("factory")
        return "quality-result-1"

    snapshot = _snapshot()
    result = _quality(snapshot, factory=factory)
    assert calls == ["factory"]
    assert result.option_chain_quality_result_id == "quality-result-1"
    assert result.option_chain_snapshot_id == snapshot.option_chain_snapshot_id


def test_default_quality_identity_is_deterministic_for_identical_snapshot_and_clock():
    snapshot = _snapshot()
    first = _quality(snapshot)
    second = _quality(snapshot)
    assert first == second
    assert first.option_chain_quality_result_id == f"option-chain-quality-{snapshot.option_chain_snapshot_id}"


@pytest.mark.parametrize(
    "name,value",
    (
        ("snapshot", "not-a-snapshot"),
        ("policy", "not-a-policy"),
        ("clock", "not-callable"),
        ("clock", lambda: datetime(2025, 1, 2)),
        ("clock", lambda: None),
        ("factory", "not-callable"),
        ("factory", lambda: ""),
        ("factory", lambda: " "),
        ("factory", lambda: 7),
    ),
)
def test_invalid_quality_controls_fail_closed(name, value):
    kwargs = {name: value}
    snapshot = kwargs.pop("snapshot", _snapshot())
    policy = kwargs.pop("policy", None)
    clock = kwargs.pop("clock", lambda: NOW)
    factory = kwargs.pop("factory", None)
    with pytest.raises(ValueError):
        _quality(snapshot, policy=policy, clock=clock, factory=factory)


def test_result_has_only_bounded_structural_quality_fields_and_no_option_intelligence():
    payload = _quality(_snapshot()).to_dict()
    assert set(payload) == {
        "option_chain_quality_result_id", "created_at", "option_chain_snapshot_id",
        "underlying_symbol", "exchange", "expiry", "quality_status", "age_seconds",
        "total_strikes", "complete_pair_count", "missing_call_count", "missing_put_count",
        "malformed_quote_count", "duplicate_strike_count", "completeness_ratio",
        "blockers", "warnings", "schema_version",
    }
    forbidden = {
        "pcr", "max_pain", "support", "resistance", "open_interest_bias",
        "volatility_skew", "gamma_exposure", "direction", "bias", "confidence",
        "selection", "ranking", "decision", "risk", "execution",
    }
    assert not forbidden.intersection(payload)


@pytest.mark.parametrize(
    "records,policy_changes",
    (
        (_records_for_shape(), {}),
        (_records_for_shape(crossed_sides=frozenset({(0, "CALL")})), {"crossed_market_behavior": "WARN"}),
        (_records_for_shape(duplicate_sides=((0, "CALL"),)), {"duplicate_strike_behavior": "WARN"}),
    ),
)
def test_quality_evaluation_never_mutates_normalizer_created_snapshots(records, policy_changes):
    snapshot = _snapshot(records=records)
    before = snapshot.to_dict()
    _quality(snapshot, policy=_policy(**policy_changes))
    assert snapshot.to_dict() == before


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_quality_preserves_each_canonical_market_identity_and_expiry(symbol, exchange):
    snapshot = _snapshot(underlying_symbol=symbol, exchange=exchange)
    result = _quality(snapshot)
    assert (result.underlying_symbol, result.exchange, result.expiry) == (symbol, exchange, EXPIRY)
    assert result.option_chain_snapshot_id == snapshot.option_chain_snapshot_id


@pytest.mark.parametrize(
    "source_timestamp,policy_changes,expected_status",
    (
        (NOW - timedelta(seconds=2), {"maximum_age_seconds": 1.0}, "STALE"),
        (NOW + timedelta(seconds=10), {"future_tolerance_seconds": 30.0}, "VALID"),
        (NOW + timedelta(microseconds=1), {"future_tolerance_seconds": 0.0}, "FUTURE"),
    ),
)
def test_age_and_future_tolerances_are_policy_driven(source_timestamp, policy_changes, expected_status):
    result = _quality(_snapshot(source_timestamp=source_timestamp), policy=_policy(**policy_changes))
    assert result.quality_status == expected_status

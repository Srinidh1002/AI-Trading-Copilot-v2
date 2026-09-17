from datetime import datetime, timedelta
import math

import pandas as pd
import pytest

from services.contracts.market_snapshot_v1 import (
    MarketSnapshotV1, SnapshotValidationError, from_core_snapshot,
    from_dashboard_snapshot, from_live_analysis_inputs, normalise_ohlcv,
    to_legacy_dashboard_dict, to_lowercase_ohlcv, to_uppercase_ohlcv,
)


NOW = datetime.fromisoformat("2026-07-25T10:00:00+05:30")


def frame(uppercase=False):
    names = ["timestamp", "open", "high", "low", "close", "volume"]
    if uppercase:
        names = ["timestamp", "Open", "High", "Low", "Close", "Volume"]
    return pd.DataFrame([["2026-07-25T09:55:00+05:30", 100, 105, 99, 104, 10]], columns=names)


def valid(**changes):
    values = dict(symbol="NIFTY", exchange="NSE", instrument_type="INDEX", captured_at=NOW, market_timestamp=NOW - timedelta(seconds=10), ltp=104.0, open=100.0, high=105.0, low=99.0, close=104.0, volume=10.0)
    values.update(changes)
    return MarketSnapshotV1(**values)


def test_valid_minimal_and_full_snapshot():
    minimal = MarketSnapshotV1(symbol="NIFTY", exchange="NSE", instrument_type="INDEX", captured_at=NOW, market_timestamp=NOW, ltp=100)
    full = valid(timeframes={"5m": normalise_ohlcv(frame(), "5m")}, option_chain_status="VALID", india_vix_status="VALID", india_vix_value=12.5, fii_dii_status="VALID", fii_dii_data={"fii": 1})
    assert minimal.validation_passed and full.validation_passed
    assert full.to_dict()["timeframes"]["5m"]["bars"][0]["close"] == 104.0


@pytest.mark.parametrize("changes", [{"symbol": ""}, {"symbol": None}, {"symbol": 42}, {"ltp": math.nan}, {"ltp": math.inf}, {"ltp": -1}, {"volume": -1}, {"schema_version": "v0"}, {"snapshot_id": ""}])
def test_invalid_critical_values_are_explicit(changes):
    snapshot = valid(**changes)
    assert snapshot.validation_passed is False
    assert snapshot.overall_status == "INVALID"


def test_invalid_timestamp_raises_documented_validation_error():
    with pytest.raises(SnapshotValidationError):
        valid(market_timestamp="not-time")


def test_option_vix_and_institutional_statuses_are_distinct():
    unavailable = valid()
    empty = valid(option_chain_status="EMPTY", option_chain_data={})
    stale = valid(option_chain_status="STALE", is_stale=True, india_vix_status="STALE", fii_dii_status="UNAVAILABLE")
    assert unavailable.option_chain_status == "UNAVAILABLE"
    assert empty.option_chain_status == "EMPTY"
    assert stale.option_chain_status == "STALE" and stale.india_vix_status == "STALE"
    assert {"option_chain", "india_vix", "fii_dii"} <= set(unavailable.missing_sources)
    assert {"option_chain", "india_vix"} <= set(stale.stale_sources)
    assert not unavailable.option_chain_available
    assert stale.option_chain_available and stale.india_vix_available


def test_option_completeness_is_explicit_and_round_trips():
    snapshot = valid(option_chain_status="VALID", option_chain_complete=False, option_chain_data={"records": []})
    rebuilt = MarketSnapshotV1.from_dict(snapshot.to_dict())
    assert snapshot.option_chain_available and rebuilt.option_chain_complete is False


def test_invalid_source_status_is_not_positive_evidence():
    snapshot = valid(option_chain_status="ready")
    assert snapshot.option_chain_status == "INVALID"
    assert any("invalid status" in warning for warning in snapshot.warnings)


def test_ohlcv_normalization_adapters_and_partial_timeframes():
    lower = normalise_ohlcv(frame(), "5m")
    upper = normalise_ohlcv(frame(uppercase=True), "1h")
    snapshot = valid(timeframes={"5m": lower, "1h": upper})
    assert list(to_lowercase_ohlcv(lower).columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert "Open" in to_uppercase_ohlcv(upper).columns
    assert set(snapshot.timeframes) == {"5m", "1h"}


def test_missing_ohlcv_columns_and_negative_volume_are_rejected():
    with pytest.raises(SnapshotValidationError):
        normalise_ohlcv(frame().drop(columns=["close"]), "5m")
    broken = frame(); broken.loc[0, "volume"] = -1
    with pytest.raises(SnapshotValidationError):
        normalise_ohlcv(broken, "5m")


def test_serialization_round_trip_and_freshness_are_deterministic():
    snapshot = valid(timeframes={"5m": normalise_ohlcv(frame(), "5m")})
    payload = snapshot.to_dict()
    rebuilt = MarketSnapshotV1.from_dict(payload)
    assert snapshot.to_json() == rebuilt.to_json()
    assert snapshot.calculate_freshness(NOW) == 10.0


def test_option_identity_validation_is_explicit():
    invalid = valid(instrument_type="OPTION", expiry="14JUL2026", strike=0, option_type="CALL")
    assert invalid.validation_passed is False
    valid_option = valid(instrument_type="OPTION", expiry="2026-07-30", strike=25000, option_type="CE")
    assert valid_option.validation_passed is True


def test_legacy_adapters_preserve_critical_fields_and_record_warnings():
    dashboard = {"symbol": "NIFTY", "history": frame(), "ltp": 104, "open": 100, "high": 105, "low": 99, "close": 104, "volume": 10, "timestamp": NOW.isoformat(), "market_status": "OPEN", "option_analysis": {}, "unknown": "legacy"}
    core = dict(dashboard, candle_time=NOW.isoformat())
    first = from_dashboard_snapshot(dashboard, reference_time=NOW)
    second = from_core_snapshot(core, reference_time=NOW)
    legacy = to_legacy_dashboard_dict(first)
    assert first.ltp == second.ltp == legacy["ltp"] == 104.0
    assert any("Unmapped" in warning for warning in first.warnings)
    assert "history" in legacy


def test_live_adapter_is_side_effect_free_and_records_invalid_frame():
    snapshot = from_live_analysis_inputs(symbol="NIFTY", exchange="NSE", market_timestamp=NOW, ltp=100, timeframes={"5m": frame(), "15m": frame().drop(columns=["volume"])}, reference_time=NOW)
    assert set(snapshot.timeframes) == {"5m"}
    assert snapshot.warnings


def test_timezone_is_explicit_and_naive_timestamps_are_interpreted_in_it():
    snapshot = valid(market_timestamp="2026-07-25T09:50:00", captured_at="2026-07-25T10:00:00")
    assert snapshot.market_timestamp.utcoffset() == timedelta(hours=5, minutes=30)
    assert snapshot.freshness_seconds == 600.0


def test_explicit_stale_freshness_marks_market_source_stale():
    snapshot = valid(freshness_seconds=61)
    assert snapshot.is_stale and snapshot.overall_status == "STALE"
    assert "market" in snapshot.stale_sources


def test_legacy_uppercase_and_lowercase_ohlcv_adapters_are_explicit():
    series = normalise_ohlcv(frame(uppercase=True), "5m")
    assert list(to_uppercase_ohlcv(series).columns) == ["timestamp", "Open", "High", "Low", "Close", "Volume"]
    assert list(to_lowercase_ohlcv(series).columns) == ["timestamp", "open", "high", "low", "close", "volume"]

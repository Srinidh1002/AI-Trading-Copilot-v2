from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.broker.provider_shadow_parity_v2 import (
    ProviderShadowParityEngineV2,
    ShadowParityThresholdsV2,
)


NOW = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)


def engine(**kwargs):
    return ProviderShadowParityEngineV2(
        ShadowParityThresholdsV2(**kwargs),
        clock=lambda: NOW,
    )


def test_quote_match_uses_fyers_as_primary():
    report = engine(quote_ltp_bps=20).compare_quote(
        "NIFTY",
        {"last_price": 23000.0},
        {"last_price": 23010.0},
    )
    assert report.primary_provider == "FYERS"
    assert report.shadow_provider == "ANGEL_SMARTAPI"
    assert report.status == "MATCH"
    assert report.evidence_complete is True


def test_quote_divergence_is_detected_without_fallback():
    report = engine(quote_ltp_bps=10).compare_quote(
        "NIFTY",
        {"last_price": 23000.0},
        {"last_price": 23100.0},
    )
    assert report.status == "DIVERGED"
    metric = next(x for x in report.metrics if x.field == "last_price")
    assert metric.within_tolerance is False


def test_quote_missing_primary_ltp_is_insufficient():
    report = engine().compare_quote(
        "SENSEX",
        {},
        {"last_price": 74000.0},
    )
    assert report.status == "INSUFFICIENT_EVIDENCE"
    assert report.evidence_complete is False


def test_timestamp_lag_is_measured_when_both_present():
    report = engine(timestamp_lag_seconds=5).compare_quote(
        "NIFTY",
        {"last_price": 23000.0, "provider_timestamp": NOW},
        {"last_price": 23000.0, "provider_timestamp": NOW.timestamp() + 7},
    )
    metric = next(x for x in report.metrics if x.field == "timestamp_lag")
    assert metric.divergence == 7.0
    assert metric.within_tolerance is False
    assert report.status == "DIVERGED"


def test_depth_compares_bid_ask_oi_volume():
    report = engine().compare_depth(
        "NIFTY",
        {"bid_price": 100.0, "ask_price": 101.0, "open_interest": 1000, "volume": 10000},
        {"bid_price": 100.1, "ask_price": 101.1, "open_interest": 1050, "volume": 11000},
    )
    assert report.evidence_complete is True
    assert {m.field for m in report.metrics} == {
        "bid_price", "ask_price", "open_interest", "volume"
    }


def test_candle_alignment_supports_iso_provider_timestamp():
    rows_a = [
        {"timestamp": NOW, "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
    ]
    rows_b = [
        {"timestamp": "2026-09-17T15:30:00+05:30", "open": 100.1, "high": 102.1, "low": 99.1, "close": 101.1, "volume": 1050},
    ]
    report = engine(candle_price_bps=20).compare_candles("NIFTY", rows_a, rows_b)
    assert report.status == "MATCH"
    assert report.evidence_complete is True


def test_candles_without_alignment_are_insufficient():
    report = engine().compare_candles(
        "NIFTY",
        [{"timestamp": NOW, "close": 100}],
        [{"timestamp": NOW.timestamp() + 60, "close": 100}],
    )
    assert report.status == "INSUFFICIENT_EVIDENCE"
    assert "NO_ALIGNED_CANDLES" in report.warnings


def test_option_chain_coverage_and_ltp_are_compared():
    primary = [
        {"expiry": "2026-09-24", "strike": 23000, "option_type": "CE", "ltp": 100, "oi": 1000},
        {"expiry": "2026-09-24", "strike": 23000, "option_type": "PE", "ltp": 90, "oi": 900},
    ]
    shadow = [
        {"expiry": "2026-09-24", "strike": 23000, "option_type": "CE", "ltp": 100.1, "oi": 1010},
        {"expiry": "2026-09-24", "strike": 23000, "option_type": "PE", "ltp": 90.1, "oi": 910},
    ]
    report = engine(minimum_chain_coverage=1.0).compare_option_chain("NIFTY", primary, shadow)
    assert report.status == "MATCH"
    coverage = next(x for x in report.metrics if x.field == "chain_coverage")
    assert coverage.divergence == 1.0


def test_low_option_chain_coverage_diverges():
    primary = [
        {"expiry": "2026-09-24", "strike": 23000, "option_type": "CE", "ltp": 100},
        {"expiry": "2026-09-24", "strike": 23000, "option_type": "PE", "ltp": 90},
    ]
    shadow = [
        {"expiry": "2026-09-24", "strike": 23000, "option_type": "CE", "ltp": 100},
    ]
    report = engine(minimum_chain_coverage=0.8).compare_option_chain("NIFTY", primary, shadow)
    assert report.status == "DIVERGED"


def test_shadow_unavailable_is_explicit_and_not_fallback():
    report = engine().shadow_unavailable("SENSEX", "QUOTE", "provider unavailable")
    assert report.status == "SHADOW_UNAVAILABLE"
    assert report.evidence_complete is False
    assert report.metrics == ()


def test_thresholds_reject_invalid_values():
    with pytest.raises(ValueError):
        ShadowParityThresholdsV2(quote_ltp_bps=-1)
    with pytest.raises(ValueError):
        ShadowParityThresholdsV2(minimum_chain_coverage=0)

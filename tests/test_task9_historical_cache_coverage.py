from datetime import datetime

from services.historical_data_cache import (
    HistoricalDataCache,
)


def _response():
    return {
        "status": True,
        "data": [
            [
                "2026-08-07T15:25:00+05:30",
                100.0,
                101.0,
                99.0,
                100.5,
                1000,
            ]
        ],
    }


def test_cache_with_sufficient_request_coverage_is_reused(
    tmp_path,
):
    cache = HistoricalDataCache(
        file_path=tmp_path / "history.json",
        time_function=lambda: 1000.0,
    )

    cache.set(
        "NSE",
        "99926000",
        "5m",
        _response(),
        requested_until=(
            "2026-08-07T15:30:00"
        ),
    )

    result = cache.get_with_metadata(
        "NSE",
        "99926000",
        "5m",
        max_age_seconds=240,
        required_until=(
            "2026-08-07T15:28:00"
        ),
    )

    assert result is not None

    assert (
        result["metadata"]["requested_until"]
        == "2026-08-07T15:30:00"
    )


def test_fresh_cache_with_old_request_window_fails_to_miss(
    tmp_path,
):
    cache = HistoricalDataCache(
        file_path=tmp_path / "history.json",
        time_function=lambda: 1000.0,
    )

    cache.set(
        "NSE",
        "99926000",
        "5m",
        _response(),
        requested_until=(
            "2026-08-07T10:00:00"
        ),
    )

    reader = HistoricalDataCache(
        file_path=cache.file_path,
        time_function=lambda: 1010.0,
    )

    result = reader.get_with_metadata(
        "NSE",
        "99926000",
        "5m",
        max_age_seconds=240,
        required_until=(
            "2026-08-07T15:00:00"
        ),
    )

    assert result is None


def test_legacy_entry_without_coverage_fails_closed_when_required(
    tmp_path,
):
    cache = HistoricalDataCache(
        file_path=tmp_path / "history.json",
        time_function=lambda: 1000.0,
    )

    cache.set(
        "NSE",
        "99926000",
        "5m",
        _response(),
    )

    assert (
        cache.get_with_metadata(
            "NSE",
            "99926000",
            "5m",
            max_age_seconds=240,
            required_until=(
                "2026-08-07T15:00:00"
            ),
        )
        is None
    )


def test_existing_callers_without_coverage_requirement_remain_compatible(
    tmp_path,
):
    cache = HistoricalDataCache(
        file_path=tmp_path / "history.json",
        time_function=lambda: 1000.0,
    )

    cache.set(
        "NSE",
        "99926000",
        "5m",
        _response(),
    )

    assert (
        cache.get(
            "NSE",
            "99926000",
            "5m",
            max_age_seconds=240,
        )
        == _response()
    )


def test_timezone_awareness_mismatch_fails_closed(
    tmp_path,
):
    cache = HistoricalDataCache(
        file_path=tmp_path / "history.json",
        time_function=lambda: 1000.0,
    )

    cache.set(
        "NSE",
        "99926000",
        "5m",
        _response(),
        requested_until=(
            "2026-08-07T15:30:00+05:30"
        ),
    )

    result = cache.get_with_metadata(
        "NSE",
        "99926000",
        "5m",
        max_age_seconds=240,
        required_until=(
            "2026-08-07T15:28:00"
        ),
    )

    assert result is None


def test_requested_until_accepts_datetime_iso_contract(
    tmp_path,
):
    requested = datetime(
        2026,
        8,
        7,
        15,
        30,
    ).isoformat()

    cache = HistoricalDataCache(
        file_path=tmp_path / "history.json",
        time_function=lambda: 1000.0,
    )

    cache.set(
        "NSE",
        "99926000",
        "5m",
        _response(),
        requested_until=requested,
    )

    result = cache.get_with_metadata(
        "NSE",
        "99926000",
        "5m",
        max_age_seconds=240,
        required_until=requested,
    )

    assert result is not None

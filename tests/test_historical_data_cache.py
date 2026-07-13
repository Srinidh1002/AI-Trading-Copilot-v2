import json

import pytest

from services.historical_data_cache import (
    HistoricalDataCache,
)


def response_data():
    return {
        "status": True,
        "data": [
            [
                "2026-07-13T09:15:00+05:30",
                24100.0,
                24120.0,
                24090.0,
                24110.0,
                100,
            ]
        ],
    }


def test_cache_persists_across_instances(
    tmp_path,
):
    file_path = (
        tmp_path
        / "historical_cache.json"
    )

    first = HistoricalDataCache(
        file_path=file_path,
        time_function=lambda: 1000.0,
    )

    first.set(
        "NSE",
        "99926000",
        "5m",
        response_data(),
    )

    second = HistoricalDataCache(
        file_path=file_path,
        time_function=lambda: 1100.0,
    )

    result = second.get(
        "NSE",
        "99926000",
        "5m",
        max_age_seconds=240.0,
    )

    assert result == response_data()


def test_expired_cache_returns_none(
    tmp_path,
):
    file_path = (
        tmp_path
        / "historical_cache.json"
    )

    cache = HistoricalDataCache(
        file_path=file_path,
        time_function=lambda: 1000.0,
    )

    cache.set(
        "NSE",
        "99926000",
        "5m",
        response_data(),
    )

    expired = HistoricalDataCache(
        file_path=file_path,
        time_function=lambda: 1300.0,
    )

    assert (
        expired.get(
            "NSE",
            "99926000",
            "5m",
            max_age_seconds=240.0,
        )
        is None
    )


def test_cache_returns_defensive_copy(
    tmp_path,
):
    cache = HistoricalDataCache(
        file_path=(
            tmp_path
            / "historical_cache.json"
        ),
        time_function=lambda: 1000.0,
    )

    cache.set(
        "NSE",
        "99926000",
        "5m",
        response_data(),
    )

    first = cache.get(
        "NSE",
        "99926000",
        "5m",
        max_age_seconds=240.0,
    )

    first["data"][0][1] = -1

    second = cache.get(
        "NSE",
        "99926000",
        "5m",
        max_age_seconds=240.0,
    )

    assert second["data"][0][1] == 24100.0


def test_empty_data_cannot_be_cached(
    tmp_path,
):
    cache = HistoricalDataCache(
        file_path=(
            tmp_path
            / "historical_cache.json"
        )
    )

    with pytest.raises(
        ValueError,
        match="Empty historical data",
    ):
        cache.set(
            "NSE",
            "99926000",
            "5m",
            {
                "status": True,
                "data": [],
            },
        )


def test_corrupt_cache_fails_to_cache_miss(
    tmp_path,
):
    file_path = (
        tmp_path
        / "historical_cache.json"
    )

    file_path.write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    cache = HistoricalDataCache(
        file_path=file_path,
    )

    assert (
        cache.get(
            "NSE",
            "99926000",
            "5m",
            max_age_seconds=240.0,
        )
        is None
    )


def test_written_document_has_expected_schema(
    tmp_path,
):
    file_path = (
        tmp_path
        / "historical_cache.json"
    )

    cache = HistoricalDataCache(
        file_path=file_path,
        time_function=lambda: 1000.0,
    )

    cache.set(
        "NSE",
        "99926000",
        "5m",
        response_data(),
    )

    document = json.loads(
        file_path.read_text(
            encoding="utf-8"
        )
    )

    assert document["version"] == 1

    assert (
        "NSE:99926000:5m"
        in document["entries"]
    )
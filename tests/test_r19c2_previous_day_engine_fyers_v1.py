from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.broker.fyers_data_compatibility_v2 import (
    FyersDataOnlyCompatibilityV2,
)
from src import previous_day_engine as previous_day_module
from src.previous_day_engine import PreviousDayEngine

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(
    2026,
    10,
    6,
    11,
    0,
    tzinfo=IST,
)


def _epoch(
    year: int,
    month: int,
    day: int,
    hour: int = 9,
    minute: int = 15,
) -> int:
    return int(
        datetime(
            year,
            month,
            day,
            hour,
            minute,
            tzinfo=IST,
        ).timestamp()
    )


class FakeCandleApi:
    def __init__(self, rows):
        self.rows = rows
        self.requests = []

    def getCandleData(self, params):
        self.requests.append(params)
        return {
            "status": True,
            "data": self.rows,
        }


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(
        previous_day_module,
        "_now_ist",
        lambda: NOW,
    )


def test_fyers_epoch_seconds_select_latest_completed_session():
    api = FakeCandleApi(
        [
            [_epoch(2026, 10, 3), 100, 110, 90, 105, 10],
            [_epoch(2026, 10, 5), 106, 112, 100, 110, 20],
            [_epoch(2026, 10, 6), 111, 113, 108, 109, 5],
        ]
    )

    result = PreviousDayEngine(api).fetch(force=True)

    assert result["status"] == "OK"
    assert result["date"] == "2026-10-05"
    assert result["open"] == 106.0
    assert result["high"] == 112.0
    assert result["low"] == 100.0
    assert result["close"] == 110.0


def test_single_completed_daily_row_is_sufficient_previous_session_evidence():
    api = FakeCandleApi(
        [
            [_epoch(2026, 10, 5), 100, 105, 98, 103, 1000],
        ]
    )

    result = PreviousDayEngine(api).fetch(force=True)

    assert result["status"] == "OK"
    assert result["date"] == "2026-10-05"
    assert result["atr14"] is None


def test_provider_order_does_not_control_previous_session_selection():
    api = FakeCandleApi(
        [
            [_epoch(2026, 10, 5), 200, 210, 190, 205, 1000],
            [_epoch(2026, 10, 2), 100, 110, 90, 105, 1000],
            [_epoch(2026, 10, 6), 300, 310, 290, 305, 1000],
            [_epoch(2026, 10, 3), 150, 160, 140, 155, 1000],
        ]
    )

    result = PreviousDayEngine(api).fetch(force=True)

    assert result["status"] == "OK"
    assert result["date"] == "2026-10-05"
    assert result["close"] == 205.0


@pytest.mark.parametrize(
    ("raw_timestamp", "expected_date"),
    (
        ("2026-10-05T09:15:00+05:30", "2026-10-05"),
        ("2026-10-05T03:45:00+00:00", "2026-10-05"),
        (str(_epoch(2026, 10, 5)), "2026-10-05"),
    ),
)
def test_iso_and_numeric_string_timestamps_are_supported(
    raw_timestamp,
    expected_date,
):
    api = FakeCandleApi(
        [
            [raw_timestamp, 100, 105, 95, 104, 100],
        ]
    )

    result = PreviousDayEngine(api).fetch(force=True)

    assert result["status"] == "OK"
    assert result["date"] == expected_date


def test_today_only_history_is_no_prior_session_not_insufficient_history():
    api = FakeCandleApi(
        [
            [_epoch(2026, 10, 6), 100, 105, 95, 104, 100],
        ]
    )

    result = PreviousDayEngine(api).fetch(force=True)

    assert result == {
        "status": "EVIDENCE_UNAVAILABLE",
        "reason": "NO_PRIOR_SESSION",
        "date": None,
        "open": None,
        "high": None,
        "low": None,
        "close": None,
        "range": None,
        "range_pct": None,
        "body_pct": None,
        "direction": None,
        "close_location": None,
        "day_type": None,
        "atr14": None,
    }


def test_unparseable_history_timestamp_fails_closed_with_specific_reason():
    api = FakeCandleApi(
        [
            ["not-a-provider-timestamp", 100, 105, 95, 104, 100],
        ]
    )

    result = PreviousDayEngine(api).fetch(force=True)

    assert result["status"] == "EVIDENCE_UNAVAILABLE"
    assert result["reason"] == "UNPARSEABLE_HISTORY_TIMESTAMP"


def test_atr_uses_only_completed_sessions_not_current_partial_daily_candle():
    api = FakeCandleApi(
        [
            [_epoch(2026, 10, 3), 100, 110, 90, 105, 1000],
            [_epoch(2026, 10, 5), 106, 112, 100, 110, 1000],
            [_epoch(2026, 10, 6), 111, 1000, 1, 500, 1],
        ]
    )

    result = PreviousDayEngine(api).fetch(force=True)

    assert result["status"] == "OK"
    assert result["date"] == "2026-10-05"
    assert result["atr14"] == 12.0


class FakeFyersHistoryClient:
    def __init__(self):
        self.history_requests = []

    def history(self, data=None):
        self.history_requests.append(data)
        return {
            "s": "ok",
            "code": 200,
            "candles": [
                [_epoch(2026, 10, 3), 100, 110, 90, 105, 1000],
                [_epoch(2026, 10, 5), 106, 112, 100, 110, 1000],
                [_epoch(2026, 10, 6), 111, 113, 108, 109, 100],
            ],
        }

    def quotes(self, data=None):
        raise AssertionError("quotes must not be called")

    def depth(self, data=None):
        raise AssertionError("depth must not be called")


def test_previous_day_engine_accepts_actual_fyers_compatibility_history_shape():
    client = FakeFyersHistoryClient()

    adapter = FyersDataOnlyCompatibilityV2(
        client=client,
        symbol_resolver=(
            lambda exchange, tradingsymbol, token:
            "NSE:NIFTY50-INDEX"
        ),
    )

    engine = PreviousDayEngine(
        adapter,
        market="NIFTY",
        index_exchange="NSE",
        index_token="99926000",
    )

    result = engine.fetch(force=True)

    assert result["status"] == "OK"
    assert result["date"] == "2026-10-05"
    assert result["close"] == 110.0

    assert len(client.history_requests) == 1

    request = client.history_requests[0]

    assert request["symbol"] == "NSE:NIFTY50-INDEX"
    assert request["resolution"] == "D"
    assert request["date_format"] == "0"
    assert isinstance(request["range_from"], int)
    assert isinstance(request["range_to"], int)
    assert request["range_to"] > request["range_from"]

from unittest.mock import MagicMock

import pytest
import requests

from services.angel_instrument_master import (
    AngelInstrumentMaster,
)


VALID_RECORDS = [
    {
        "token": "1001",
        "symbol": "NIFTY27AUG2624500CE",
        "name": "NIFTY",
        "expiry": "27AUG2026",
        "strike": "2450000.000000",
        "lotsize": "75",
        "instrumenttype": "OPTIDX",
        "exch_seg": "NFO",
    }
]


def _normal_response():
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = VALID_RECORDS
    return response


def _range_response(
    *,
    start,
    end,
    total,
    body,
):
    response = MagicMock()
    response.status_code = 206
    response.raise_for_status.return_value = None
    response.headers = {
        "Content-Range": (
            f"bytes {start}-{end}/{total}"
        ),
        "Content-Length": str(
            len(body)
        ),
        "Accept-Ranges": "bytes",
    }
    response.content = body
    return response


def test_master_successful_normal_request_does_not_use_ranges():
    session = MagicMock()
    session.get.return_value = (
        _normal_response()
    )

    master = AngelInstrumentMaster(
        session=session,
        time_function=lambda: 1000.0,
    )

    result = master.fetch_instruments()

    assert result == VALID_RECORDS
    assert session.get.call_count == 1

    call = session.get.call_args

    assert call.kwargs == {
        "timeout": 30,
    }


def test_master_transport_failure_falls_back_to_complete_ranges():
    import json

    encoded = json.dumps(
        VALID_RECORDS
    ).encode(
        "utf-8"
    )

    session = MagicMock()

    session.get.side_effect = [
        requests.exceptions.ChunkedEncodingError(
            "premature response end"
        ),
        _range_response(
            start=0,
            end=len(encoded) - 1,
            total=len(encoded),
            body=encoded,
        ),
    ]

    master = AngelInstrumentMaster(
        session=session,
        time_function=lambda: 1000.0,
    )

    result = master.fetch_instruments()

    assert result == VALID_RECORDS
    assert session.get.call_count == 2

    ranged_call = (
        session.get.call_args_list[1]
    )

    assert ranged_call.kwargs[
        "headers"
    ] == {
        "Range": (
            "bytes=0-1048575"
        ),
        "Accept-Encoding": "identity",
    }


def test_master_invalid_normal_json_falls_back_to_ranges():
    import json

    encoded = json.dumps(
        VALID_RECORDS
    ).encode(
        "utf-8"
    )

    first = MagicMock()
    first.raise_for_status.return_value = None
    first.json.side_effect = ValueError(
        "truncated JSON"
    )

    session = MagicMock()
    session.get.side_effect = [
        first,
        _range_response(
            start=0,
            end=len(encoded) - 1,
            total=len(encoded),
            body=encoded,
        ),
    ]

    master = AngelInstrumentMaster(
        session=session,
        time_function=lambda: 1000.0,
    )

    assert (
        master.fetch_instruments()
        == VALID_RECORDS
    )

    assert session.get.call_count == 2


def test_range_request_retries_same_segment_after_transport_failure(
    monkeypatch,
):
    import json

    encoded = json.dumps(
        VALID_RECORDS
    ).encode(
        "utf-8"
    )

    session = MagicMock()

    session.get.side_effect = [
        requests.ConnectionError(
            "normal transfer unavailable"
        ),
        requests.ReadTimeout(
            "temporary range timeout"
        ),
        _range_response(
            start=0,
            end=len(encoded) - 1,
            total=len(encoded),
            body=encoded,
        ),
    ]

    sleeps = []

    monkeypatch.setattr(
        "services.angel_instrument_master.time.sleep",
        lambda seconds: sleeps.append(
            seconds
        ),
    )

    master = AngelInstrumentMaster(
        session=session,
        time_function=lambda: 1000.0,
    )

    assert (
        master.fetch_instruments()
        == VALID_RECORDS
    )

    assert sleeps == [1.0]

    first_range = (
        session.get.call_args_list[1]
    )

    second_range = (
        session.get.call_args_list[2]
    )

    assert (
        first_range.kwargs["headers"]
        == second_range.kwargs["headers"]
    )


def test_range_transport_rejects_http_200_response():
    session = MagicMock()

    bad_range = MagicMock()
    bad_range.status_code = 200
    bad_range.raise_for_status.return_value = None
    bad_range.headers = {
        "Content-Length": "100",
    }
    bad_range.content = b"x" * 100

    session.get.side_effect = [
        requests.ConnectionError(
            "normal transfer unavailable"
        ),
        bad_range,
    ]

    master = AngelInstrumentMaster(
        session=session,
        time_function=lambda: 1000.0,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "did not return HTTP 206"
        ),
    ):
        master.fetch_instruments()


def test_range_transport_rejects_wrong_content_range():
    session = MagicMock()

    bad_range = _range_response(
        start=1,
        end=3,
        total=4,
        body=b"abc",
    )

    session.get.side_effect = [
        requests.ConnectionError(
            "normal transfer unavailable"
        ),
        bad_range,
    ]

    master = AngelInstrumentMaster(
        session=session,
        time_function=lambda: 1000.0,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "does not match the requested byte range"
        ),
    ):
        master.fetch_instruments()


def test_range_transport_rejects_changed_total_size():
    first_body = b"a" * (
        1024 * 1024
    )

    second_body = b"b"

    session = MagicMock()

    session.get.side_effect = [
        requests.ConnectionError(
            "normal transfer unavailable"
        ),
        _range_response(
            start=0,
            end=(1024 * 1024) - 1,
            total=(1024 * 1024) + 1,
            body=first_body,
        ),
        _range_response(
            start=1024 * 1024,
            end=1024 * 1024,
            total=(1024 * 1024) + 2,
            body=second_body,
        ),
    ]

    master = AngelInstrumentMaster(
        session=session,
        time_function=lambda: 1000.0,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "total size changed"
        ),
    ):
        master.fetch_instruments()


def test_range_transport_fails_after_three_attempts(
    monkeypatch,
):
    session = MagicMock()

    session.get.side_effect = [
        requests.ConnectionError(
            "normal transfer unavailable"
        ),
        requests.ReadTimeout("one"),
        requests.ReadTimeout("two"),
        requests.ReadTimeout("three"),
    ]

    sleeps = []

    monkeypatch.setattr(
        "services.angel_instrument_master.time.sleep",
        lambda seconds: sleeps.append(
            seconds
        ),
    )

    master = AngelInstrumentMaster(
        session=session,
        time_function=lambda: 1000.0,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "range request failed after "
            "3 attempts: ReadTimeout"
        ),
    ):
        master.fetch_instruments()

    assert sleeps == [
        1.0,
        2.0,
    ]


def test_range_transport_rejects_oversized_declared_master():
    session = MagicMock()

    body = b"x"

    response = _range_response(
        start=0,
        end=0,
        total=(128 * 1024 * 1024) + 1,
        body=body,
    )

    # Requested range is much larger than one byte, so construct an
    # intentionally malformed Content-Range that would be rejected before
    # any allocation or continuation.
    response.headers[
        "Content-Range"
    ] = (
        "bytes 0-1048575/"
        f"{(128 * 1024 * 1024) + 1}"
    )

    response.content = (
        b"x" * (1024 * 1024)
    )
    response.headers[
        "Content-Length"
    ] = str(
        1024 * 1024
    )

    session.get.side_effect = [
        requests.ConnectionError(
            "normal transfer unavailable"
        ),
        response,
    ]

    master = AngelInstrumentMaster(
        session=session,
        time_function=lambda: 1000.0,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "outside the permitted range"
        ),
    ):
        master.fetch_instruments()

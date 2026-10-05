from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services.certification.task8_live_paper_default_composition import (
    _capture_parent_spot_quotes_from_bundle,
    _validate_retained_task8_evaluations,
    build_task8_dependencies,
)


def _decision(*statuses):
    entries = tuple(
        SimpleNamespace(
            child=SimpleNamespace(
                observation_id=observation_id,
                terminal_status=status,
            )
        )
        for observation_id, status in statuses
    )
    return SimpleNamespace(entries=entries)


def test_default_factory_is_exposed_without_running_live_reads():
    assert callable(build_task8_dependencies)


def test_completed_children_require_exact_retained_evaluations():
    decision = _decision(
        ("nifty-observation", "COMPLETED"),
        ("sensex-observation", "COMPLETED"),
    )

    _validate_retained_task8_evaluations(
        decision,
        {
            "nifty-observation": object(),
            "sensex-observation": object(),
        },
    )


def test_failed_child_does_not_require_typed_evaluation():
    decision = _decision(
        ("nifty-observation", "COMPLETED"),
        ("sensex-observation", "FAILED"),
    )

    _validate_retained_task8_evaluations(
        decision,
        {
            "nifty-observation": object(),
        },
    )


def test_unavailable_child_does_not_require_typed_evaluation():
    decision = _decision(
        ("nifty-observation", "UNAVAILABLE"),
        ("sensex-observation", "COMPLETED"),
    )

    _validate_retained_task8_evaluations(
        decision,
        {
            "sensex-observation": object(),
        },
    )


def test_missing_completed_evaluation_fails_closed():
    decision = _decision(
        ("nifty-observation", "COMPLETED"),
        ("sensex-observation", "COMPLETED"),
    )

    with pytest.raises(
        RuntimeError,
        match="completed children",
    ):
        _validate_retained_task8_evaluations(
            decision,
            {
                "nifty-observation": object(),
            },
        )


def test_failed_child_must_not_have_unexpected_retained_evaluation():
    decision = _decision(
        ("nifty-observation", "COMPLETED"),
        ("sensex-observation", "FAILED"),
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected",
    ):
        _validate_retained_task8_evaluations(
            decision,
            {
                "nifty-observation": object(),
                "sensex-observation": object(),
            },
        )


def _provider_bundle(quote_reader):
    return SimpleNamespace(quote_reader=quote_reader)


def test_parent_spot_capture_uses_injected_provider_exactly_once_per_market():
    market_ts = datetime(2026, 10, 5, 4, 30, tzinfo=timezone.utc)
    received = market_ts + timedelta(seconds=1)
    calls = []

    def quote_reader(exchange, symboltoken, underlying):
        calls.append((exchange, symboltoken, underlying))
        price = 22500.0 if underlying == "NIFTY" else 72000.0
        return {
            "spot_price": price,
            "market_timestamp": market_ts,
            "received_at": received,
            "timestamp_source": "TEST_PROVIDER_TIMESTAMP",
            "provider": "TEST_DATA_ONLY",
        }

    result = _capture_parent_spot_quotes_from_bundle(
        _provider_bundle(quote_reader)
    )

    assert len(calls) == 2
    assert calls[0][0] == "NSE"
    assert calls[0][2] == "NIFTY"
    assert calls[1][0] == "BSE"
    assert calls[1][2] == "SENSEX"
    assert result[("NIFTY", "NSE")]["spot_price"] == 22500.0
    assert result[("SENSEX", "BSE")]["spot_price"] == 72000.0
    assert all(
        item["timestamp_source"] == "TEST_PROVIDER_TIMESTAMP"
        for item in result.values()
    )


def test_parent_spot_capture_rejects_missing_provider_timestamp():
    received = datetime(2026, 10, 5, 4, 30, tzinfo=timezone.utc)

    def quote_reader(*_args):
        return {
            "spot_price": 22500.0,
            "market_timestamp": None,
            "received_at": received,
            "timestamp_source": "TEST_PROVIDER_TIMESTAMP",
        }

    with pytest.raises(ValueError, match="market timestamp"):
        _capture_parent_spot_quotes_from_bundle(
            _provider_bundle(quote_reader)
        )


def test_parent_spot_capture_rejects_receipt_before_provider_timestamp():
    market_ts = datetime(2026, 10, 5, 4, 30, tzinfo=timezone.utc)

    def quote_reader(*_args):
        return {
            "spot_price": 22500.0,
            "market_timestamp": market_ts,
            "received_at": market_ts - timedelta(seconds=1),
            "timestamp_source": "TEST_PROVIDER_TIMESTAMP",
        }

    with pytest.raises(ValueError, match="receipt precedes"):
        _capture_parent_spot_quotes_from_bundle(
            _provider_bundle(quote_reader)
        )


def test_task8_parent_composition_has_no_direct_provider_client_import():
    source = (
        __import__("pathlib").Path(
            "services/certification/task8_live_paper_default_composition.py"
        ).read_text(encoding="utf-8")
    )
    assert "get_certification_market_client" not in source
    assert "fetch_canonical_two_market_full_quotes" not in source

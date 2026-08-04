from datetime import datetime, timezone

import pytest

from services.paper_orchestration.unavailable_external_context_readers import (
    UnavailableGlobalMarketReader,
    UnavailableInstitutionalFlowReader,
    UnavailableScheduledEventReader,
)


NOW = datetime(
    2026,
    8,
    4,
    8,
    0,
    tzinfo=timezone.utc,
)


def test_unavailable_readers_return_only_explicit_absence():
    global_reader = UnavailableGlobalMarketReader()
    institutional_reader = UnavailableInstitutionalFlowReader()
    event_reader = UnavailableScheduledEventReader()

    assert global_reader(NOW) == ()
    assert institutional_reader(NOW) is None
    assert event_reader(NOW) == ()

    assert global_reader.call_count == 1
    assert institutional_reader.call_count == 1
    assert event_reader.call_count == 1


@pytest.mark.parametrize(
    "reader",
    (
        UnavailableGlobalMarketReader(),
        UnavailableInstitutionalFlowReader(),
        UnavailableScheduledEventReader(),
    ),
)
def test_unavailable_readers_require_aware_time(reader):
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        reader(NOW.replace(tzinfo=None))


def test_unavailable_readers_do_not_use_network_or_legacy_engines():
    source = __import__("pathlib").Path(
        "services/paper_orchestration/"
        "unavailable_external_context_readers.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "requests",
        "yfinance",
        "urlopen",
        "fii_dii_engine",
        "economic_calendar_engine",
        "NSE_TRADING_HOLIDAYS_2026",
        "BSE_TRADING_HOLIDAYS_2026",
        "date.today()",
    ):
        assert forbidden not in source

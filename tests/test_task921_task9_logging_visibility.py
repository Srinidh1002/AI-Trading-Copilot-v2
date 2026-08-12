import io
import logging

from services.certification.task9_live_paper_certification_launcher import (
    _HISTORICAL_DIAGNOSTIC_HANDLER_MARKER,
    configure_task9_historical_diagnostic_logging,
)


def test_task9_launcher_historical_diagnostic_logging_is_visible_and_idempotent():
    target = logging.getLogger("services.market.live_multi_timeframe_data")
    previous_level = target.level
    previous_propagate = target.propagate
    existing = list(target.handlers)
    stream = io.StringIO()

    try:
        for handler in existing:
            target.removeHandler(handler)

        configure_task9_historical_diagnostic_logging(stream=stream)
        configure_task9_historical_diagnostic_logging(stream=stream)
        target.info(
            "historical_provider_request exchange=NSE symboltoken=99926000 "
            "timeframe=5m mode=INCREMENTAL fromdate=2026-07-10 10:05 "
            "todate=2026-07-10 10:20 required_closed_at=2026-07-10T10:15:00+05:30"
        )

        lines = stream.getvalue().splitlines()
        assert len(lines) == 1
        assert lines[0].startswith("historical_provider_request exchange=NSE")
        assert "api_key" not in lines[0].lower()
        assert "totp" not in lines[0].lower()
        assert target.propagate is False
        assert target.level == logging.INFO
        assert sum(
            bool(getattr(handler, _HISTORICAL_DIAGNOSTIC_HANDLER_MARKER, False))
            for handler in target.handlers
        ) == 1
    finally:
        for handler in list(target.handlers):
            target.removeHandler(handler)
        for handler in existing:
            target.addHandler(handler)
        target.setLevel(previous_level)
        target.propagate = previous_propagate

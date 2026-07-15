from pathlib import Path


RUNNER_PATH = Path(
    "live_option_decision_nifty.py"
)


def _runner_content():
    return RUNNER_PATH.read_text(
        encoding="utf-8"
    )


def test_live_runner_uses_market_session_configuration():
    content = _runner_content()

    assert (
        "resolve_market_session_configuration"
        in content
    )

    assert (
        "MARKET_SESSION_CONFIGURATION"
        in content
    )

    assert (
        "MARKET_HOLIDAY_CALENDAR"
        in content
    )


def test_live_runner_has_no_direct_nse_calendar_getter():
    content = _runner_content()

    assert (
        "get_nse_holiday_calendar"
        not in content
    )


def test_live_runner_has_no_direct_nse_holiday_calendar_variable():
    content = _runner_content()

    assert (
        "NSE_HOLIDAY_CALENDAR"
        not in content
    )


def test_live_runner_passes_resolved_calendar_to_session_guard():
    content = _runner_content()

    expected = """            holiday_calendar=(
                MARKET_HOLIDAY_CALENDAR
            ),"""

    assert (
        expected
        in content
    )


def test_live_runner_session_configuration_uses_selected_underlying():
    content = _runner_content()

    expected = """    resolve_market_session_configuration(
        UNDERLYING
    )"""

    assert (
        expected
        in content
    )


def test_live_runner_preserves_option_exchange_routing():
    content = _runner_content()

    assert (
        "option_exchange=OPTION_EXCHANGE"
        in content
    )


def test_live_runner_preserves_spot_exchange_routing():
    content = _runner_content()

    expected = """            exchange_tokens={
                SPOT_EXCHANGE: [
                    SPOT_SYMBOLTOKEN
                ]
            }"""

    assert (
        expected
        in content
    )

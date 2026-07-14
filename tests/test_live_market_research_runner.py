from datetime import datetime, time
from pathlib import Path
from unittest.mock import patch

import pytest

import live_market_research_runner as runner


def build_fake_now():
    return datetime(
        2026,
        7,
        16,
        10,
        0,
        tzinfo=runner.IST,
    )


class SuccessfulCompletedProcess:
    returncode = 0


class FailedCompletedProcess:
    returncode = 1


def test_default_configuration():
    assert runner.DEFAULT_INTERVAL_SECONDS == 300
    assert runner.DEFAULT_START_TIME == "09:15"
    assert runner.DEFAULT_END_TIME == "15:30"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("09:15", time(9, 15)),
        ("9:15", time(9, 15)),
        ("15:30", time(15, 30)),
        ("00:00", time(0, 0)),
        ("23:59", time(23, 59)),
    ],
)
def test_parse_clock(value, expected):
    assert runner.parse_clock(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "invalid",
        "09",
        "09:15:00",
        "25:00",
        "12:60",
    ],
)
def test_parse_clock_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        runner.parse_clock(value)


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (9, 14, False),
        (9, 15, True),
        (12, 0, True),
        (15, 30, True),
        (15, 31, False),
    ],
)
def test_is_within_session(
    hour,
    minute,
    expected,
):
    current = datetime(
        2026,
        7,
        16,
        hour,
        minute,
    )

    result = runner.is_within_session(
        current,
        time(9, 15),
        time(15, 30),
    )

    assert result is expected


def test_seconds_until_next_cycle_returns_interval():
    assert (
        runner.seconds_until_next_cycle(300)
        == 300
    )


def test_build_argument_parser_defaults():
    parser = runner.build_argument_parser()

    args = parser.parse_args([])

    assert args.interval_seconds == 300
    assert args.start_time == "09:15"
    assert args.end_time == "15:30"
    assert args.max_cycles is None


def test_build_argument_parser_custom_values():
    parser = runner.build_argument_parser()

    args = parser.parse_args(
        [
            "--interval-seconds",
            "60",
            "--start-time",
            "10:00",
            "--end-time",
            "11:00",
            "--max-cycles",
            "5",
        ]
    )

    assert args.interval_seconds == 60
    assert args.start_time == "10:00"
    assert args.end_time == "11:00"
    assert args.max_cycles == 5


def test_run_live_cycle_uses_current_python():
    completed = object()

    with patch(
        "live_market_research_runner.subprocess.run",
        return_value=completed,
    ) as mock_run:

        result = runner.run_live_cycle()

    assert result is completed

    mock_run.assert_called_once_with(
        [
            runner.sys.executable,
            "-u",
            str(runner.LIVE_ENTRY_POINT),
        ],
        check=False,
    )


def test_live_entry_point_targets_nifty_script():
    assert runner.LIVE_ENTRY_POINT == Path(
        "live_option_decision_nifty.py"
    )


def test_current_ist_datetime_is_timezone_aware():
    result = runner.current_ist_datetime()

    assert result.tzinfo is not None
    assert result.utcoffset() is not None


def test_main_runs_one_controlled_cycle(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        runner,
        "current_ist_datetime",
        build_fake_now,
    )

    monkeypatch.setattr(
        runner,
        "run_live_cycle",
        lambda: SuccessfulCompletedProcess(),
    )

    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: True,
    )

    monkeypatch.setattr(
        runner.sys,
        "argv",
        [
            "live_market_research_runner.py",
            "--interval-seconds",
            "1",
            "--max-cycles",
            "1",
        ],
    )

    runner.main()

    output = capsys.readouterr().out

    assert "MARKET RESEARCH CYCLE 1" in output
    assert "Cycle Exit Code: 0" in output
    assert "Maximum cycle count reached." in output
    assert "Completed Cycles: 1" in output


def test_main_survives_child_cycle_error(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        runner,
        "current_ist_datetime",
        build_fake_now,
    )

    monkeypatch.setattr(
        runner,
        "run_live_cycle",
        lambda: FailedCompletedProcess(),
    )

    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: True,
    )

    monkeypatch.setattr(
        runner.sys,
        "argv",
        [
            "live_market_research_runner.py",
            "--max-cycles",
            "1",
        ],
    )

    runner.main()

    output = capsys.readouterr().out

    assert "Cycle Exit Code: 1" in output
    assert (
        "The continuous runner remains active."
        in output
    )
    assert "Completed Cycles: 1" in output


def test_main_rejects_zero_interval(
    monkeypatch,
):
    monkeypatch.setattr(
        runner.sys,
        "argv",
        [
            "live_market_research_runner.py",
            "--interval-seconds",
            "0",
        ],
    )

    with pytest.raises(SystemExit):
        runner.main()


def test_main_rejects_negative_max_cycles(
    monkeypatch,
):
    monkeypatch.setattr(
        runner.sys,
        "argv",
        [
            "live_market_research_runner.py",
            "--max-cycles",
            "-1",
        ],
    )

    with pytest.raises(SystemExit):
        runner.main()


def test_main_rejects_reversed_session_window(
    monkeypatch,
):
    monkeypatch.setattr(
        runner.sys,
        "argv",
        [
            "live_market_research_runner.py",
            "--start-time",
            "15:30",
            "--end-time",
            "09:15",
        ],
    )

    with pytest.raises(SystemExit):
        runner.main()


def test_main_rejects_missing_live_entry_point(
    monkeypatch,
):
    monkeypatch.setattr(
        runner.sys,
        "argv",
        [
            "live_market_research_runner.py",
        ],
    )

    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: False,
    )

    with pytest.raises(
        SystemExit,
        match="Live entry point not found",
    ):
        runner.main()
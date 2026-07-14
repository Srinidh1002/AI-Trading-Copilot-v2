from copy import deepcopy

import pytest

import market_session_summary as runner


class FakeJournal:
    def __init__(
        self,
        entries,
    ):
        self.entries = deepcopy(
            entries
        )
        self.requested_dates = []

    def read_entries(
        self,
        session_date,
    ):
        self.requested_dates.append(
            session_date
        )

        return deepcopy(
            self.entries
        )


class FakeEngine:
    def __init__(
        self,
        result=None,
    ):
        self.result = (
            deepcopy(
                result
            )
            if result is not None
            else {
                "status": "COMPLETED",
                "read_only": True,
            }
        )

        self.calls = []

    def summarize(
        self,
        entries,
        *,
        session_date=None,
    ):
        self.calls.append(
            {
                "entries": deepcopy(
                    entries
                ),
                "session_date": (
                    session_date
                ),
            }
        )

        return deepcopy(
            self.result
        )


def make_summary():
    return {
        "status": "COMPLETED",
        "read_only": True,
        "session_date": "2026-07-15",
        "cycles_observed": 3,
        "decisions": {
            "distribution": {
                "NO_TRADE": 2,
                "TRADE_READY": 1,
            },
            "dominant": "NO_TRADE",
        },
        "market_decisions": {
            "distribution": {
                "NO_TRADE": 2,
                "TRADE_READY": 1,
            },
            "dominant": "NO_TRADE",
        },
        "directions": {
            "distribution": {
                "BEARISH": 2,
                "BULLISH": 1,
            },
            "dominant": "BEARISH",
        },
        "regimes": {
            "distribution": {
                "TRENDING_BEARISH": 3,
            },
            "dominant": "TRENDING_BEARISH",
        },
        "strategies": {
            "distribution": {
                "TREND_CONTINUATION": 3,
            },
            "dominant": "TREND_CONTINUATION",
        },
        "confidence": {
            "observations": 3,
            "average": 80.0,
            "minimum": 70.0,
            "maximum": 90.0,
        },
        "risk_flags": {
            "Weak volume": 2,
        },
        "setups": {
            "distribution": {
                "NO_SETUP": 2,
                "SETUP_READY": 1,
            },
            "dominant": "NO_SETUP",
        },
        "paper_trading": {
            "opened": 1,
            "not_opened": 2,
            "status_distribution": {
                "SKIPPED": 2,
                "OPENED": 1,
            },
        },
        "decision_transitions": {
            "count": 1,
            "distribution": {
                (
                    "NO_TRADE -> "
                    "TRADE_READY"
                ): 1,
            },
        },
        "trade_ready_timing": {
            "count": 1,
            "first_timestamp": (
                "2026-07-15T09:30:00+05:30"
            ),
            "last_timestamp": (
                "2026-07-15T09:30:00+05:30"
            ),
        },
        "session_timing": {
            "first_timestamp": (
                "2026-07-15T09:15:00+05:30"
            ),
            "last_timestamp": (
                "2026-07-15T09:30:00+05:30"
            ),
            "duration_seconds": 900.0,
        },
        "market_session_statuses": {
            "distribution": {
                "SESSION_VALID": 3,
            },
            "dominant": "SESSION_VALID",
        },
    }


def test_resolve_explicit_session_date():
    assert (
        runner.resolve_session_date(
            "2026-07-15"
        )
        == "2026-07-15"
    )


def test_resolve_session_date_strips_spaces():
    assert (
        runner.resolve_session_date(
            " 2026-07-15 "
        )
        == "2026-07-15"
    )


def test_empty_session_date_rejected():
    with pytest.raises(
        ValueError,
        match=(
            "session_date cannot be empty"
        ),
    ):
        runner.resolve_session_date(
            " "
        )


def test_invalid_session_date_rejected():
    with pytest.raises(
        ValueError,
        match=(
            "session_date must use "
            "YYYY-MM-DD format"
        ),
    ):
        runner.resolve_session_date(
            "15-07-2026"
        )


def test_build_summary_reads_requested_date():
    journal = FakeJournal(
        [
            {
                "decision": "NO_TRADE",
            },
        ]
    )

    engine = FakeEngine(
        {
            "status": "COMPLETED",
        }
    )

    result = runner.build_summary(
        "2026-07-15",
        journal=journal,
        engine=engine,
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED"
    )

    assert (
        journal.requested_dates
        == [
            "2026-07-15",
        ]
    )


def test_build_summary_passes_entries_to_engine():
    entries = [
        {
            "decision": "NO_TRADE",
        },
    ]

    journal = FakeJournal(
        entries
    )

    engine = FakeEngine()

    runner.build_summary(
        "2026-07-15",
        journal=journal,
        engine=engine,
    )

    assert (
        engine.calls
        == [
            {
                "entries": entries,
                "session_date": (
                    "2026-07-15"
                ),
            },
        ]
    )


def test_print_summary_contains_header(
    capsys,
):
    runner.print_summary(
        make_summary()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "AI TRADING COPILOT"
        in output
    )

    assert (
        "MARKET SESSION SUMMARY"
        in output
    )


def test_print_summary_contains_cycle_count(
    capsys,
):
    runner.print_summary(
        make_summary()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Cycles Observed: 3"
        in output
    )


def test_print_summary_contains_decisions(
    capsys,
):
    runner.print_summary(
        make_summary()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "NO_TRADE: 2"
        in output
    )

    assert (
        "TRADE_READY: 1"
        in output
    )


def test_print_summary_contains_direction(
    capsys,
):
    runner.print_summary(
        make_summary()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Dominant Direction: BEARISH"
        in output
    )


def test_print_summary_contains_regime(
    capsys,
):
    runner.print_summary(
        make_summary()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        (
            "Dominant Regime: "
            "TRENDING_BEARISH"
        )
        in output
    )


def test_print_summary_contains_confidence(
    capsys,
):
    runner.print_summary(
        make_summary()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Average: 80.0"
        in output
    )


def test_print_summary_contains_risk_flags(
    capsys,
):
    runner.print_summary(
        make_summary()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Weak volume: 2"
        in output
    )


def test_print_summary_contains_paper_stats(
    capsys,
):
    runner.print_summary(
        make_summary()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Opened: 1"
        in output
    )

    assert (
        "Not Opened: 2"
        in output
    )


def test_print_summary_contains_transitions(
    capsys,
):
    runner.print_summary(
        make_summary()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Transitions: 1"
        in output
    )

    assert (
        (
            "NO_TRADE -> "
            "TRADE_READY: 1"
        )
        in output
    )


def test_print_summary_contains_trade_ready_timing(
    capsys,
):
    runner.print_summary(
        make_summary()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Occurrences: 1"
        in output
    )

    assert (
        (
            "First: "
            "2026-07-15T09:30:00+05:30"
        )
        in output
    )


def test_print_summary_contains_read_only_safety(
    capsys,
):
    runner.print_summary(
        make_summary()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "READ-ONLY MARKET INTELLIGENCE"
        in output
    )

    assert (
        "NO REAL ORDER WAS PLACED"
        in output
    )


def test_main_success(
    monkeypatch,
    capsys,
):
    summary = make_summary()

    monkeypatch.setattr(
        runner,
        "build_summary",
        lambda session_date=None: summary,
    )

    result = runner.main(
        [
            "--date",
            "2026-07-15",
        ]
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert result == 0

    assert (
        "SESSION SUMMARY COMPLETE"
        in output
    )


def test_main_value_error_returns_one(
    monkeypatch,
    capsys,
):
    def fail(
        session_date=None,
    ):
        raise ValueError(
            "Broken summary"
        )

    monkeypatch.setattr(
        runner,
        "build_summary",
        fail,
    )

    result = runner.main(
        [
            "--date",
            "2026-07-15",
        ]
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert result == 1

    assert (
        "SESSION SUMMARY FAILED"
        in output
    )

    assert (
        "Broken summary"
        in output
    )


def test_main_os_error_returns_one(
    monkeypatch,
    capsys,
):
    def fail(
        session_date=None,
    ):
        raise OSError(
            "Cannot read journal"
        )

    monkeypatch.setattr(
        runner,
        "build_summary",
        fail,
    )

    result = runner.main(
        [
            "--date",
            "2026-07-15",
        ]
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert result == 1

    assert (
        "Cannot read journal"
        in output
    )
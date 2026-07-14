"""
Tests for cross_session_research CLI.

The CLI is presentation-only.

IMPORTANT:
- READ ONLY.
- RESEARCH ONLY.
- NO BROKER EXECUTION.
- NO ORDER PLACEMENT.
"""

import sys

import cross_session_research as cli


def build_result():
    return {
        "status": "COMPLETED",
        "read_only": True,
        "research_only": True,
        "start_date": "2026-07-14",
        "end_date": "2026-07-15",
        "archive_status": "COMPLETED",
        "reports_loaded": 2,
        "archive_errors": [],
        "component_errors": [],
        "intelligence": {
            "status": "COMPLETED",
            "read_only": True,
            "research_only": True,
            "sessions_observed": 2,
            "session_dates": [
                "2026-07-14",
                "2026-07-15",
            ],
            "decision_intelligence": {
                "distribution": [],
                "dominant": None,
                "transitions": [],
                "longest_streak": {
                    "decision": None,
                    "sessions": 0,
                    "start_index": None,
                    "end_index": None,
                },
            },
            "direction_intelligence": {
                "distribution": [],
                "dominant": None,
                "transitions": [],
                "longest_streak": {
                    "direction": None,
                    "sessions": 0,
                    "start_index": None,
                    "end_index": None,
                },
            },
            "regime_intelligence": {
                "distribution": [],
                "dominant": None,
                "transitions": [],
                "longest_streak": {
                    "regime": None,
                    "sessions": 0,
                    "start_index": None,
                    "end_index": None,
                },
            },
            "confidence_intelligence": {
                "observations": 0,
                "first": None,
                "final": None,
                "minimum": None,
                "maximum": None,
                "average": None,
                "change": None,
                "trend": "UNAVAILABLE",
                "series": [],
            },
            "readiness_intelligence": {
                "observations": 0,
                "first": None,
                "final": None,
                "minimum": None,
                "maximum": None,
                "average": None,
                "change": None,
                "trend": "UNAVAILABLE",
                "series": [],
            },
            "risk_flag_intelligence": {
                "observations": 0,
                "first": None,
                "final": None,
                "minimum": None,
                "maximum": None,
                "average": None,
                "change": None,
                "trend": "UNAVAILABLE",
                "series": [],
            },
            "setup_score_intelligence": {
                "observations": 0,
                "first": None,
                "final": None,
                "minimum": None,
                "maximum": None,
                "average": None,
                "change": None,
                "trend": "UNAVAILABLE",
                "series": [],
            },
            "blocker_recurrence": [],
            "final_blocker_recurrence": [],
            "trade_ready_intelligence": {
                "sessions_observed": 2,
                "trade_ready_sessions": 0,
                "trade_ready_frequency_percent": 0.0,
                "first_trade_ready_session": None,
                "last_trade_ready_session": None,
            },
            "strategy_regime_observations": {
                "positive": [],
                "negative": [],
            },
            "research_observations": [
                (
                    "No archived session observed "
                    "a TRADE_READY state."
                ),
            ],
            "session_records": [],
        },
    }


def test_build_parser_accepts_no_dates():
    parser = cli.build_parser()

    args = parser.parse_args(
        []
    )

    assert args.start_date is None
    assert args.end_date is None


def test_build_parser_accepts_start_date():
    parser = cli.build_parser()

    args = parser.parse_args(
        [
            "--start-date",
            "2026-07-14",
        ]
    )

    assert (
        args.start_date
        == "2026-07-14"
    )


def test_build_parser_accepts_end_date():
    parser = cli.build_parser()

    args = parser.parse_args(
        [
            "--end-date",
            "2026-07-15",
        ]
    )

    assert (
        args.end_date
        == "2026-07-15"
    )


def test_build_parser_accepts_date_range():
    parser = cli.build_parser()

    args = parser.parse_args(
        [
            "--start-date",
            "2026-07-14",
            "--end-date",
            "2026-07-15",
        ]
    )

    assert (
        args.start_date
        == "2026-07-14"
    )

    assert (
        args.end_date
        == "2026-07-15"
    )


def test_print_report_prints_title(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "CROSS-SESSION RESEARCH"
        in output
    )


def test_print_report_prints_read_only_mode(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Mode: READ ONLY"
        in output
    )


def test_print_report_prints_research_only(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Research Only: True"
        in output
    )


def test_print_report_prints_date_range(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Start Date: 2026-07-14"
        in output
    )

    assert (
        "End Date: 2026-07-15"
        in output
    )


def test_print_report_prints_runner_status(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Runner Status: COMPLETED"
        in output
    )


def test_print_report_prints_archive_status(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Archive Status: COMPLETED"
        in output
    )


def test_print_report_prints_reports_loaded(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Reports Loaded: 2"
        in output
    )


def test_print_report_prints_sessions_observed(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Sessions Observed: 2"
        in output
    )


def test_print_report_prints_session_dates(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Session Dates: "
        "2026-07-14, 2026-07-15"
        in output
    )


def test_print_report_prints_decision_section(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "DECISION INTELLIGENCE"
        in output
    )


def test_print_report_prints_direction_section(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "DIRECTION INTELLIGENCE"
        in output
    )


def test_print_report_prints_regime_section(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "REGIME INTELLIGENCE"
        in output
    )


def test_print_report_prints_confidence_section(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "CONFIDENCE INTELLIGENCE"
        in output
    )


def test_print_report_prints_readiness_section(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "READINESS INTELLIGENCE"
        in output
    )


def test_print_report_prints_risk_flag_section(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "RISK FLAG INTELLIGENCE"
        in output
    )


def test_print_report_prints_setup_score_section(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "SETUP SCORE INTELLIGENCE"
        in output
    )


def test_print_report_prints_blocker_section(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "BLOCKER RECURRENCE"
        in output
    )


def test_print_report_prints_trade_ready_section(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "TRADE READY INTELLIGENCE"
        in output
    )


def test_print_report_prints_trade_ready_frequency(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Trade Ready Frequency %: 0.0"
        in output
    )


def test_print_report_prints_strategy_regime_section(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "STRATEGY-REGIME OBSERVATIONS"
        in output
    )


def test_print_report_prints_research_observations(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "No archived session observed "
        "a TRADE_READY state."
        in output
    )


def test_print_report_prints_completion_boundary(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "CROSS-SESSION RESEARCH COMPLETE"
        in output
    )


def test_print_report_prints_no_real_order_boundary(
    capsys,
):
    cli.print_report(
        build_result()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "NO REAL ORDER WAS PLACED"
        in output
    )


def test_print_report_handles_missing_intelligence(
    capsys,
):
    result = build_result()

    result["intelligence"] = None

    cli.print_report(
        result
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Sessions Observed: None"
        in output
    )


def test_print_report_handles_empty_result(
    capsys,
):
    cli.print_report(
        {}
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "CROSS-SESSION RESEARCH"
        in output
    )

    assert (
        "NO REAL ORDER WAS PLACED"
        in output
    )


def test_print_distribution_handles_invalid_data(
    capsys,
):
    cli._print_distribution(
        "TEST",
        None,
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert "Unavailable" in output


def test_print_numeric_intelligence_handles_invalid_data(
    capsys,
):
    cli._print_numeric_intelligence(
        "TEST",
        None,
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert "Unavailable" in output


def test_main_forwards_dates_to_runner(
    monkeypatch,
    capsys,
):
    calls = []

    class FakeRunner:
        def run(
            self,
            *,
            start_date=None,
            end_date=None,
        ):
            calls.append(
                {
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )

            return build_result()

    monkeypatch.setattr(
        cli,
        "CrossSessionResearchRunner",
        FakeRunner,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cross_session_research.py",
            "--start-date",
            "2026-07-14",
            "--end-date",
            "2026-07-15",
        ],
    )

    cli.main()

    capsys.readouterr()

    assert calls == [
        {
            "start_date": "2026-07-14",
            "end_date": "2026-07-15",
        }
    ]


def test_main_prints_runner_result(
    monkeypatch,
    capsys,
):
    class FakeRunner:
        def run(
            self,
            *,
            start_date=None,
            end_date=None,
        ):
            return build_result()

    monkeypatch.setattr(
        cli,
        "CrossSessionResearchRunner",
        FakeRunner,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cross_session_research.py",
        ],
    )

    cli.main()

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Runner Status: COMPLETED"
        in output
    )


def test_cli_has_no_execution_functions():
    forbidden_names = {
        "place_order",
        "execute_order",
        "submit_order",
        "buy",
        "sell",
    }

    assert forbidden_names.isdisjoint(
        set(
            dir(
                cli
            )
        )
    )
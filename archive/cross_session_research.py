"""
Cross-Session Research CLI.

Loads archived daily research reports and produces
read-only cross-session market research intelligence.

IMPORTANT:
- READ ONLY.
- RESEARCH ONLY.
- NO BROKER LOGIN.
- NO MARKET DATA REQUEST.
- NO PAPER TRADE MUTATION.
- NO REAL ORDER PLACEMENT.
- NO STRATEGY TUNING.
"""

import argparse
import json

from services.cross_session_research_runner import (
    CrossSessionResearchRunner,
)


def build_parser():
    """
    Build command-line argument parser.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Run read-only cross-session "
            "market research intelligence."
        )
    )

    parser.add_argument(
        "--start-date",
        default=None,
        help=(
            "Optional first archived session date "
            "in YYYY-MM-DD format."
        ),
    )

    parser.add_argument(
        "--end-date",
        default=None,
        help=(
            "Optional last archived session date "
            "in YYYY-MM-DD format."
        ),
    )

    return parser


def _print_distribution(
    title,
    intelligence,
):
    """
    Print a categorical intelligence distribution.
    """

    print(
        f"\n{title}"
    )

    print(
        "-" * len(
            title
        )
    )

    if not isinstance(
        intelligence,
        dict,
    ):
        print(
            "Unavailable"
        )
        return

    distribution = (
        intelligence.get(
            "distribution",
            [],
        )
    )

    if not distribution:
        print(
            "None"
        )

    else:
        for item in distribution:
            if not isinstance(
                item,
                dict,
            ):
                continue

            label = None

            for key in (
                "decision",
                "direction",
                "regime",
            ):
                if key in item:
                    label = item.get(
                        key
                    )
                    break

            print(
                f"- {label}: "
                f"{item.get('count', 0)}"
            )

    dominant = intelligence.get(
        "dominant"
    )

    print(
        "Dominant:",
        (
            json.dumps(
                dominant,
                ensure_ascii=False,
                sort_keys=True,
            )
            if dominant is not None
            else None
        ),
    )

    transitions = intelligence.get(
        "transitions",
        [],
    )

    print(
        "Transitions:",
        len(
            transitions
        )
        if isinstance(
            transitions,
            list,
        )
        else 0,
    )

    longest_streak = intelligence.get(
        "longest_streak"
    )

    print(
        "Longest Streak:",
        (
            json.dumps(
                longest_streak,
                ensure_ascii=False,
                sort_keys=True,
            )
            if longest_streak is not None
            else None
        ),
    )


def _print_numeric_intelligence(
    title,
    intelligence,
):
    """
    Print numeric cross-session intelligence.
    """

    print(
        f"\n{title}"
    )

    print(
        "-" * len(
            title
        )
    )

    if not isinstance(
        intelligence,
        dict,
    ):
        print(
            "Unavailable"
        )
        return

    print(
        "Observations:",
        intelligence.get(
            "observations"
        ),
    )

    print(
        "First:",
        intelligence.get(
            "first"
        ),
    )

    print(
        "Final:",
        intelligence.get(
            "final"
        ),
    )

    print(
        "Minimum:",
        intelligence.get(
            "minimum"
        ),
    )

    print(
        "Maximum:",
        intelligence.get(
            "maximum"
        ),
    )

    print(
        "Average:",
        intelligence.get(
            "average"
        ),
    )

    print(
        "Change:",
        intelligence.get(
            "change"
        ),
    )

    print(
        "Trend:",
        intelligence.get(
            "trend"
        ),
    )


def print_report(
    result,
):
    """
    Print human-readable cross-session research.
    """

    print(
        "\n================================"
    )

    print(
        "AI TRADING COPILOT"
    )

    print(
        "CROSS-SESSION RESEARCH"
    )

    print(
        "================================"
    )

    print(
        "\nMode: READ ONLY"
    )

    print(
        "Research Only:",
        result.get(
            "research_only"
        ),
    )

    print(
        "Start Date:",
        result.get(
            "start_date"
        ),
    )

    print(
        "End Date:",
        result.get(
            "end_date"
        ),
    )

    print(
        "Runner Status:",
        result.get(
            "status"
        ),
    )

    print(
        "Archive Status:",
        result.get(
            "archive_status"
        ),
    )

    print(
        "Reports Loaded:",
        result.get(
            "reports_loaded"
        ),
    )

    intelligence = result.get(
        "intelligence",
        {},
    )

    if not isinstance(
        intelligence,
        dict,
    ):
        intelligence = {}

    print(
        "Sessions Observed:",
        intelligence.get(
            "sessions_observed"
        ),
    )

    session_dates = intelligence.get(
        "session_dates",
        [],
    )

    print(
        "Session Dates:",
        (
            ", ".join(
                str(
                    value
                )
                for value in session_dates
            )
            if session_dates
            else "None"
        ),
    )

    _print_distribution(
        "DECISION INTELLIGENCE",
        intelligence.get(
            "decision_intelligence"
        ),
    )

    _print_distribution(
        "DIRECTION INTELLIGENCE",
        intelligence.get(
            "direction_intelligence"
        ),
    )

    _print_distribution(
        "REGIME INTELLIGENCE",
        intelligence.get(
            "regime_intelligence"
        ),
    )

    _print_numeric_intelligence(
        "CONFIDENCE INTELLIGENCE",
        intelligence.get(
            "confidence_intelligence"
        ),
    )

    _print_numeric_intelligence(
        "READINESS INTELLIGENCE",
        intelligence.get(
            "readiness_intelligence"
        ),
    )

    _print_numeric_intelligence(
        "RISK FLAG INTELLIGENCE",
        intelligence.get(
            "risk_flag_intelligence"
        ),
    )

    _print_numeric_intelligence(
        "SETUP SCORE INTELLIGENCE",
        intelligence.get(
            "setup_score_intelligence"
        ),
    )

    print(
        "\nBLOCKER RECURRENCE"
    )

    print(
        "------------------"
    )

    blockers = intelligence.get(
        "blocker_recurrence",
        [],
    )

    if not blockers:
        print(
            "None"
        )

    else:
        for blocker in blockers:
            print(
                "-",
                json.dumps(
                    blocker,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )

    print(
        "\nFINAL BLOCKER RECURRENCE"
    )

    print(
        "------------------------"
    )

    final_blockers = intelligence.get(
        "final_blocker_recurrence",
        [],
    )

    if not final_blockers:
        print(
            "None"
        )

    else:
        for blocker in final_blockers:
            print(
                "-",
                json.dumps(
                    blocker,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )

    print(
        "\nTRADE READY INTELLIGENCE"
    )

    print(
        "------------------------"
    )

    trade_ready = intelligence.get(
        "trade_ready_intelligence",
        {},
    )

    if not isinstance(
        trade_ready,
        dict,
    ):
        trade_ready = {}

    print(
        "Sessions Observed:",
        trade_ready.get(
            "sessions_observed"
        ),
    )

    print(
        "Trade Ready Sessions:",
        trade_ready.get(
            "trade_ready_sessions"
        ),
    )

    print(
        "Trade Ready Frequency %:",
        trade_ready.get(
            "trade_ready_frequency_percent"
        ),
    )

    print(
        "First Trade Ready Session:",
        (
            json.dumps(
                trade_ready.get(
                    "first_trade_ready_session"
                ),
                ensure_ascii=False,
                sort_keys=True,
            )
            if trade_ready.get(
                "first_trade_ready_session"
            )
            is not None
            else None
        ),
    )

    print(
        "Last Trade Ready Session:",
        (
            json.dumps(
                trade_ready.get(
                    "last_trade_ready_session"
                ),
                ensure_ascii=False,
                sort_keys=True,
            )
            if trade_ready.get(
                "last_trade_ready_session"
            )
            is not None
            else None
        ),
    )

    print(
        "\nSTRATEGY-REGIME OBSERVATIONS"
    )

    print(
        "----------------------------"
    )

    strategy_regime = intelligence.get(
        "strategy_regime_observations",
        {},
    )

    if not isinstance(
        strategy_regime,
        dict,
    ):
        strategy_regime = {}

    positive = strategy_regime.get(
        "positive",
        [],
    )

    negative = strategy_regime.get(
        "negative",
        [],
    )

    print(
        "Positive:"
    )

    if not positive:
        print(
            "None"
        )

    else:
        for item in positive:
            print(
                "-",
                json.dumps(
                    item,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )

    print(
        "Negative:"
    )

    if not negative:
        print(
            "None"
        )

    else:
        for item in negative:
            print(
                "-",
                json.dumps(
                    item,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )

    print(
        "\nRESEARCH OBSERVATIONS"
    )

    print(
        "---------------------"
    )

    observations = intelligence.get(
        "research_observations",
        [],
    )

    if not observations:
        print(
            "None"
        )

    else:
        for observation in observations:
            print(
                "-",
                observation,
            )

    archive_errors = result.get(
        "archive_errors",
        [],
    )

    component_errors = result.get(
        "component_errors",
        [],
    )

    if archive_errors:
        print(
            "\nARCHIVE ERRORS"
        )

        print(
            "--------------"
        )

        for error in archive_errors:
            print(
                "-",
                json.dumps(
                    error,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )

    if component_errors:
        print(
            "\nCOMPONENT ERRORS"
        )

        print(
            "----------------"
        )

        for error in component_errors:
            print(
                "-",
                json.dumps(
                    error,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )

    print(
        "\n================================"
    )

    print(
        "CROSS-SESSION RESEARCH COMPLETE"
    )

    print(
        "================================"
    )

    print(
        "\nREAD-ONLY MARKET RESEARCH"
    )

    print(
        "NO REAL ORDER WAS PLACED"
    )


def main():
    """
    CLI entry point.
    """

    parser = build_parser()

    args = parser.parse_args()

    runner = (
        CrossSessionResearchRunner()
    )

    result = runner.run(
        start_date=args.start_date,
        end_date=args.end_date,
    )

    print_report(
        result
    )


if __name__ == "__main__":
    main()
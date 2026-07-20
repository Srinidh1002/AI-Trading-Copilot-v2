"""
Market Session Summary Runner.

Reads persisted MarketCycleJournal entries and produces a
human-readable end-of-session market intelligence report.

Architecture:

MarketCycleJournal
    -> data/market_sessions/YYYY-MM-DD/cycles.jsonl
        -> MarketSessionSummaryEngine
            -> human-readable session report

IMPORTANT:
- READ ONLY.
- DOES NOT authorize trades.
- DOES NOT reject trades.
- DOES NOT modify live pipeline state.
- DOES NOT modify paper-trading state.
- DOES NOT place real orders.
"""

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from services.market_cycle_journal import (
    MarketCycleJournal,
)
from services.market_session_summary import (
    MarketSessionSummaryEngine,
)


INDIA_TIMEZONE = ZoneInfo(
    "Asia/Kolkata"
)


def resolve_session_date(
    session_date=None,
):
    """
    Resolve the requested market session date.
    """

    if session_date is not None:
        normalized = str(
            session_date
        ).strip()

        if not normalized:
            raise ValueError(
                "session_date cannot be empty."
            )

        try:
            parsed = datetime.strptime(
                normalized,
                "%Y-%m-%d",
            )

        except ValueError as exc:
            raise ValueError(
                "session_date must use YYYY-MM-DD format."
            ) from exc

        return parsed.date().isoformat()

    return (
        datetime.now(
            INDIA_TIMEZONE
        )
        .date()
        .isoformat()
    )


def build_summary(
    session_date=None,
    *,
    journal=None,
    engine=None,
):
    """
    Read journal entries and build one session summary.
    """

    resolved_session_date = (
        resolve_session_date(
            session_date
        )
    )

    if journal is None:
        journal = (
            MarketCycleJournal()
        )

    if engine is None:
        engine = (
            MarketSessionSummaryEngine()
        )

    entries = journal.read_entries(
        resolved_session_date
    )

    return engine.summarize(
        entries,
        session_date=(
            resolved_session_date
        ),
    )


def _print_distribution(
    distribution,
):
    if not distribution:
        print(
            "None"
        )
        return

    for (
        label,
        count,
    ) in distribution.items():
        print(
            f"{label}: {count}"
        )


def _print_optional_value(
    value,
):
    if value is None:
        return "None"

    return str(
        value
    )


def print_summary(
    summary,
):
    """
    Print one human-readable session report.
    """

    print(
        "\n================================"
    )
    print(
        "AI TRADING COPILOT"
    )
    print(
        "MARKET SESSION SUMMARY"
    )
    print(
        "================================"
    )

    print(
        "\nMode: READ ONLY"
    )

    print(
        "Session:",
        summary.get(
            "session_date"
        ),
    )

    print(
        "Cycles Observed:",
        summary.get(
            "cycles_observed",
            0,
        ),
    )

    print(
        "\nDECISIONS"
    )
    print(
        "---------"
    )

    _print_distribution(
        summary.get(
            "decisions",
            {},
        ).get(
            "distribution",
            {},
        )
    )

    print(
        "Dominant Decision:",
        _print_optional_value(
            summary.get(
                "decisions",
                {},
            ).get(
                "dominant"
            )
        ),
    )

    print(
        "\nMARKET DECISIONS"
    )
    print(
        "----------------"
    )

    _print_distribution(
        summary.get(
            "market_decisions",
            {},
        ).get(
            "distribution",
            {},
        )
    )

    print(
        "Dominant Market Decision:",
        _print_optional_value(
            summary.get(
                "market_decisions",
                {},
            ).get(
                "dominant"
            )
        ),
    )

    print(
        "\nDIRECTIONS"
    )
    print(
        "----------"
    )

    _print_distribution(
        summary.get(
            "directions",
            {},
        ).get(
            "distribution",
            {},
        )
    )

    print(
        "Dominant Direction:",
        _print_optional_value(
            summary.get(
                "directions",
                {},
            ).get(
                "dominant"
            )
        ),
    )

    print(
        "\nMARKET REGIMES"
    )
    print(
        "--------------"
    )

    _print_distribution(
        summary.get(
            "regimes",
            {},
        ).get(
            "distribution",
            {},
        )
    )

    print(
        "Dominant Regime:",
        _print_optional_value(
            summary.get(
                "regimes",
                {},
            ).get(
                "dominant"
            )
        ),
    )

    print(
        "\nSTRATEGIES"
    )
    print(
        "----------"
    )

    _print_distribution(
        summary.get(
            "strategies",
            {},
        ).get(
            "distribution",
            {},
        )
    )

    print(
        "Dominant Strategy:",
        _print_optional_value(
            summary.get(
                "strategies",
                {},
            ).get(
                "dominant"
            )
        ),
    )

    direction_confidence = summary.get(
        "direction_confidence",
        summary.get(
            "confidence",
            {},
        ),
    )

    print(
        "\nDIRECTION CONFIDENCE"
    )
    print(
        "--------------------"
    )

    print(
        "Observations:",
        direction_confidence.get(
            "observations",
            0,
        ),
    )

    print(
        "Average:",
        _print_optional_value(
            direction_confidence.get(
                "average"
            )
        ),
    )

    print(
        "Minimum:",
        _print_optional_value(
            direction_confidence.get(
                "minimum"
            )
        ),
    )

    print(
        "Maximum:",
        _print_optional_value(
            direction_confidence.get(
                "maximum"
            )
        ),
    )

    evidence_strength = summary.get(
        "evidence_strength",
        {},
    )

    print(
        "\nEVIDENCE STRENGTH"
    )
    print(
        "-----------------"
    )

    print(
        "Observations:",
        evidence_strength.get(
            "observations",
            0,
        ),
    )

    print(
        "Average:",
        _print_optional_value(
            evidence_strength.get(
                "average"
            )
        ),
    )

    print(
        "Minimum:",
        _print_optional_value(
            evidence_strength.get(
                "minimum"
            )
        ),
    )

    print(
        "Maximum:",
        _print_optional_value(
            evidence_strength.get(
                "maximum"
            )
        ),
    )

    evidence_strength_labels = summary.get(
        "evidence_strength_labels",
        {},
    )

    print(
        "Label Distribution:"
    )

    _print_distribution(
        evidence_strength_labels.get(
            "distribution",
            {},
        )
    )

    print(
        "Dominant Label:",
        _print_optional_value(
            evidence_strength_labels.get(
                "dominant"
            )
        ),
    )

    print(
        "\nRISK FLAGS"
    )
    print(
        "----------"
    )

    _print_distribution(
        summary.get(
            "risk_flags",
            {},
        )
    )

    print(
        "\nSETUPS"
    )
    print(
        "------"
    )

    _print_distribution(
        summary.get(
            "setups",
            {},
        ).get(
            "distribution",
            {},
        )
    )

    paper_trading = summary.get(
        "paper_trading",
        {},
    )

    print(
        "\nPAPER TRADING"
    )
    print(
        "-------------"
    )

    print(
        "Opened:",
        paper_trading.get(
            "opened",
            0,
        ),
    )

    print(
        "Not Opened:",
        paper_trading.get(
            "not_opened",
            0,
        ),
    )

    print(
        "Status Distribution:"
    )

    _print_distribution(
        paper_trading.get(
            "status_distribution",
            {},
        )
    )

    transitions = summary.get(
        "decision_transitions",
        {},
    )

    print(
        "\nDECISION TRANSITIONS"
    )
    print(
        "--------------------"
    )

    print(
        "Transitions:",
        transitions.get(
            "count",
            0,
        ),
    )

    _print_distribution(
        transitions.get(
            "distribution",
            {},
        )
    )

    trade_ready = summary.get(
        "trade_ready_timing",
        {},
    )

    print(
        "\nTRADE READY TIMING"
    )
    print(
        "------------------"
    )

    print(
        "Occurrences:",
        trade_ready.get(
            "count",
            0,
        ),
    )

    print(
        "First:",
        _print_optional_value(
            trade_ready.get(
                "first_timestamp"
            )
        ),
    )

    print(
        "Last:",
        _print_optional_value(
            trade_ready.get(
                "last_timestamp"
            )
        ),
    )

    session_timing = summary.get(
        "session_timing",
        {},
    )

    print(
        "\nSESSION TIMING"
    )
    print(
        "--------------"
    )

    print(
        "First Cycle:",
        _print_optional_value(
            session_timing.get(
                "first_timestamp"
            )
        ),
    )

    print(
        "Last Cycle:",
        _print_optional_value(
            session_timing.get(
                "last_timestamp"
            )
        ),
    )

    print(
        "Observed Duration Seconds:",
        _print_optional_value(
            session_timing.get(
                "duration_seconds"
            )
        ),
    )

    print(
        "\n================================"
    )
    print(
        "SESSION SUMMARY COMPLETE"
    )
    print(
        "================================"
    )

    print(
        "\nREAD-ONLY MARKET INTELLIGENCE"
    )
    print(
        "NO REAL ORDER WAS PLACED"
    )


def create_argument_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Summarize one persisted market session."
        )
    )

    parser.add_argument(
        "--date",
        dest="session_date",
        default=None,
        help=(
            "Market session date in YYYY-MM-DD format. "
            "Defaults to the current India date."
        ),
    )

    return parser


def main(
    argv=None,
):
    parser = create_argument_parser()

    args = parser.parse_args(
        argv
    )

    try:
        summary = build_summary(
            args.session_date
        )

    except (
        ValueError,
        OSError,
    ) as exc:
        print(
            "\n================================"
        )
        print(
            "SESSION SUMMARY FAILED"
        )
        print(
            "================================"
        )

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print(
            "\nREAD-ONLY MARKET INTELLIGENCE"
        )
        print(
            "NO REAL ORDER WAS PLACED"
        )

        return 1

    print_summary(
        summary
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
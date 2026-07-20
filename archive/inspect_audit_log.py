#!/usr/bin/env python3
"""
Command-line tool to inspect audit logs.

Read-only inspection of persistent decision audit records.

Example usage:

    python inspect_audit_log.py
    python inspect_audit_log.py --limit 20
    python inspect_audit_log.py --decision TRADE_ALLOWED
    python inspect_audit_log.py --underlying NIFTY --limit 20
    python inspect_audit_log.py --summary
    python inspect_audit_log.py --file custom/path/audit.jsonl
"""

import argparse
import sys
from pathlib import Path

from services.decision_audit_logger import (
    DecisionAuditLogger,
)


def format_timestamp(
    timestamp_str,
):
    """
    Format a timestamp for display.

    Shows the last 19 characters for readability:
    "2026-07-12T14:30:00".
    """

    if not timestamp_str:
        return "N/A"

    if len(
        timestamp_str
    ) >= 19:
        return timestamp_str[:19]

    return timestamp_str


def format_record(
    record,
):
    """
    Extract displayable fields from an audit record.

    Returns a dict with formatted columns.
    """

    metadata = record.get(
        "metadata",
        {},
    )

    return {
        "logged_at": format_timestamp(
            record.get(
                "logged_at"
            )
        ),
        "underlying": metadata.get(
            "underlying",
            "N/A",
        ),
        "spot_price": metadata.get(
            "spot_price",
            "N/A",
        ),
        "decision": record.get(
            "final_decision",
            "N/A",
        ),
        "events": record.get(
            "event_count",
            0,
        ),
    }


def print_table(
    records,
):
    """
    Print audit records as a formatted table.
    """

    if not records:
        print(
            "No audit records found."
        )
        return

    print()
    print(
        "Recent Audit Records"
    )
    print(
        "="
        * 100
    )

    # Header
    print(
        "{:<20} {:<15} {:<15} {:<20} {:<10}".format(
            "Logged At",
            "Underlying",
            "Spot Price",
            "Decision",
            "Events",
        )
    )

    print(
        "="
        * 100
    )

    # Rows
    for record in records:

        formatted = format_record(
            record
        )

        spot_price = formatted[
            "spot_price"
        ]

        if (
            isinstance(
                spot_price,
                (
                    int,
                    float,
                ),
            )
        ):
            spot_price = f"{spot_price:.2f}"

        else:
            spot_price = str(
                spot_price
            )

        print(
            "{:<20} {:<15} {:<15} {:<20} {:<10}".format(
                formatted["logged_at"],
                formatted["underlying"],
                spot_price,
                formatted["decision"],
                formatted["events"],
            )
        )

    print(
        "="
        * 100
    )
    print()


def print_statistics(
    stats,
):
    """
    Print summary statistics.
    """

    total = stats.get(
        "total_records",
        0,
    )

    if total == 0:
        print(
            "No audit records found."
        )
        return

    print()
    print(
        "Audit Summary Statistics"
    )
    print(
        "="
        * 60
    )

    print(
        f"Total Records: {total}"
    )

    earliest = stats.get(
        "earliest_logged_at"
    )

    latest = stats.get(
        "latest_logged_at"
    )

    if earliest:
        print(
            f"Earliest: "
            f"{format_timestamp(earliest)}"
        )

    if latest:
        print(
            f"Latest: "
            f"{format_timestamp(latest)}"
        )

    print()

    count_by_decision = stats.get(
        "count_by_decision",
        {},
    )

    if count_by_decision:

        print(
            "Decisions:"
        )

        for (
            decision,
            count,
        ) in sorted(
            count_by_decision.items()
        ):
            print(
                f"  {decision}: {count}"
            )

        print()

    count_by_underlying = stats.get(
        "count_by_underlying",
        {},
    )

    if count_by_underlying:

        print(
            "Underlyings:"
        )

        for (
            underlying,
            count,
        ) in sorted(
            count_by_underlying.items()
        ):
            print(
                f"  {underlying}: {count}"
            )

        print()

    print(
        "="
        * 60
    )
    print()


def parse_arguments():
    """
    Parse command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Inspect audit logs for trading "
            "decision records."
        ),
        formatter_class=(
            argparse
            .RawDescriptionHelpFormatter
        ),
        epilog=(
            "Examples:\n"
            "  python inspect_audit_log.py\n"
            "  python inspect_audit_log.py "
            "--limit 20\n"
            "  python inspect_audit_log.py "
            "--decision TRADE_ALLOWED\n"
            "  python inspect_audit_log.py "
            "--underlying NIFTY --limit 20\n"
            "  python inspect_audit_log.py "
            "--summary\n"
            "  python inspect_audit_log.py "
            "--file custom/path/audit.jsonl"
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Maximum records to return "
            "(default: 10 for records, "
            "all for statistics)."
        ),
    )

    parser.add_argument(
        "--decision",
        type=str,
        default=None,
        help=(
            "Filter by final decision "
            "(e.g., TRADE_ALLOWED, NO_TRADE)."
        ),
    )

    parser.add_argument(
        "--underlying",
        type=str,
        default=None,
        help=(
            "Filter by underlying asset "
            "(e.g., NIFTY, BANKNIFTY)."
        ),
    )

    parser.add_argument(
        "--start-time",
        type=str,
        default=None,
        help=(
            "ISO 8601 start timestamp "
            "(e.g., 2026-07-12T10:00:00+00:00)."
        ),
    )

    parser.add_argument(
        "--end-time",
        type=str,
        default=None,
        help=(
            "ISO 8601 end timestamp "
            "(e.g., 2026-07-12T15:00:00+00:00)."
        ),
    )

    parser.add_argument(
        "--summary",
        action="store_true",
        help=(
            "Show summary statistics "
            "instead of records."
        ),
    )

    parser.add_argument(
        "--file",
        type=str,
        default=(
            "data/audit/"
            "decision_audit.jsonl"
        ),
        help=(
            "Path to audit log file "
            "(default: data/audit/decision_audit.jsonl)."
        ),
    )

    return parser.parse_args()


def main():
    """
    Main entry point.
    """

    args = parse_arguments()

    # Determine default limit
    if args.limit is None:
        limit = 10 if not args.summary else None

    else:
        limit = args.limit

    try:

        logger = DecisionAuditLogger(
            file_path=args.file
        )

        if args.summary:

            stats = (
                logger
                .get_summary_statistics(
                    limit=limit,
                    final_decision=(
                        args.decision
                    ),
                    underlying=(
                        args.underlying
                    ),
                    start_time=(
                        args.start_time
                    ),
                    end_time=(
                        args.end_time
                    ),
                )
            )

            print_statistics(
                stats
            )

            return 0

        else:

            records = (
                logger
                .query_records(
                    limit=limit,
                    final_decision=(
                        args.decision
                    ),
                    underlying=(
                        args.underlying
                    ),
                    start_time=(
                        args.start_time
                    ),
                    end_time=(
                        args.end_time
                    ),
                )
            )

            print_table(
                records
            )

            return 0

    except ValueError as exc:

        print(
            f"Error: {exc}",
            file=sys.stderr,
        )

        return 1

    except Exception as exc:

        print(
            f"Unexpected error: {exc}",
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    sys.exit(
        main()
    )

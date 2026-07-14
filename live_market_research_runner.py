"""
Continuous live market research runner.

Runs the existing NIFTY live option decision entry point at a
controlled interval for chronological market research capture.

The runner does not place real orders.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")

DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_START_TIME = "09:15"
DEFAULT_END_TIME = "15:30"

LIVE_ENTRY_POINT = Path(
    "live_option_decision_nifty.py"
)


def parse_clock(value: str):
    """Parse an HH:MM clock value."""

    return datetime.strptime(
        value,
        "%H:%M",
    ).time()


def current_ist_datetime():
    """Return the current timezone-aware IST datetime."""

    return datetime.now(IST)


def is_within_session(
    current_datetime,
    start_time,
    end_time,
):
    """Return whether the current time is inside the run window."""

    current_time = current_datetime.time().replace(
        tzinfo=None
    )

    return (
        start_time
        <= current_time
        <= end_time
    )


def seconds_until_next_cycle(
    interval_seconds,
):
    """Return the configured cycle wait duration."""

    return interval_seconds


def run_live_cycle():
    """Run one existing live decision cycle."""

    command = [
        sys.executable,
        "-u",
        str(LIVE_ENTRY_POINT),
    ]

    return subprocess.run(
        command,
        check=False,
    )


def build_argument_parser():
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Continuous read-only market research runner."
        )
    )

    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
    )

    parser.add_argument(
        "--start-time",
        default=DEFAULT_START_TIME,
    )

    parser.add_argument(
        "--end-time",
        default=DEFAULT_END_TIME,
    )

    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
    )

    return parser


def main():
    """Run continuous chronological market research cycles."""

    parser = build_argument_parser()
    args = parser.parse_args()

    if args.interval_seconds <= 0:
        parser.error(
            "--interval-seconds must be greater than zero"
        )

    if (
        args.max_cycles is not None
        and args.max_cycles <= 0
    ):
        parser.error(
            "--max-cycles must be greater than zero"
        )

    start_time = parse_clock(
        args.start_time
    )

    end_time = parse_clock(
        args.end_time
    )

    if start_time > end_time:
        parser.error(
            "--start-time must not be after --end-time"
        )

    if not LIVE_ENTRY_POINT.is_file():
        raise SystemExit(
            f"Live entry point not found: "
            f"{LIVE_ENTRY_POINT}"
        )

    print(
        "\n================================"
    )
    print(
        "AI TRADING COPILOT"
    )
    print(
        "CONTINUOUS MARKET RESEARCH"
    )
    print(
        "================================"
    )

    print(
        "\nMode: READ ONLY"
    )
    print(
        "Research Capture: ENABLED"
    )
    print(
        "Real Orders: DISABLED"
    )
    print(
        "Interval Seconds:",
        args.interval_seconds,
    )
    print(
        "Start Time:",
        args.start_time,
    )
    print(
        "End Time:",
        args.end_time,
    )
    print(
        "Max Cycles:",
        args.max_cycles,
    )

    completed_cycles = 0

    try:

        while True:

            now = current_ist_datetime()

            if now.time().replace(
                tzinfo=None
            ) > end_time:

                print(
                    "\nMarket research window completed."
                )

                break

            if not is_within_session(
                now,
                start_time,
                end_time,
            ):

                print(
                    "\nWaiting for research window."
                )
                print(
                    "Current IST:",
                    now.isoformat(),
                )

                time.sleep(
                    min(
                        args.interval_seconds,
                        60,
                    )
                )

                continue

            cycle_number = (
                completed_cycles + 1
            )

            print(
                "\n================================"
            )
            print(
                f"MARKET RESEARCH CYCLE "
                f"{cycle_number}"
            )
            print(
                "================================"
            )

            print(
                "Cycle Time IST:",
                now.isoformat(),
            )

            result = run_live_cycle()

            completed_cycles += 1

            print(
                "\nCycle Exit Code:",
                result.returncode,
            )

            if result.returncode != 0:

                print(
                    "Cycle completed with an error."
                )
                print(
                    "The continuous runner remains active."
                )

            if (
                args.max_cycles is not None
                and completed_cycles
                >= args.max_cycles
            ):

                print(
                    "\nMaximum cycle count reached."
                )

                break

            wait_seconds = (
                seconds_until_next_cycle(
                    args.interval_seconds
                )
            )

            print(
                "Next Cycle In Seconds:",
                wait_seconds,
            )

            time.sleep(
                wait_seconds
            )

    except KeyboardInterrupt:

        print(
            "\nContinuous market research stopped "
            "by operator."
        )

    print(
        "\n================================"
    )
    print(
        "CONTINUOUS RESEARCH COMPLETE"
    )
    print(
        "================================"
    )

    print(
        "Completed Cycles:",
        completed_cycles,
    )
    print(
        "READ-ONLY MARKET RESEARCH"
    )
    print(
        "NO REAL ORDER WAS PLACED"
    )


if __name__ == "__main__":
    main()
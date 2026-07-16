"""Day 1 non-invasive live-runner harness.

Runs ``live_option_decision_nifty.py`` on five-minute NSE time slots, stores
the unmodified console stream for every attempt, and creates a concise session
summary.  It never imports or modifies the production trading runner.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, time as clock_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = clock_time(9, 15)
MARKET_CLOSE = clock_time(15, 30)
RUNNER = "live_option_decision_nifty.py"

SUMMARY_COLUMNS = [
    "run_timestamp",
    "scheduled_time",
    "status",
    "exit_code",
    "exception",
    "spot_price",
    "decision",
    "direction",
    "confidence",
    "evidence_strength",
    "regime",
    "trend",
    "candle_timestamp",
    "candle_age_minutes",
    "support",
    "resistance",
    "paper_trading_status",
    "raw_log",
]


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run and summarize the Day 1 paper-trading session."
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=240,
        help="Maximum time allowed for one runner invocation.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one immediate invocation, then generate the report.",
    )
    return parser.parse_args()


def next_run_time(now):
    """Return the next five-minute slot within the current NSE session."""

    session_open = datetime.combine(now.date(), MARKET_OPEN, INDIA_TIMEZONE)
    session_close = datetime.combine(now.date(), MARKET_CLOSE, INDIA_TIMEZONE)

    if now <= session_open:
        return session_open

    if now > session_close:
        return None

    candidate = now.replace(second=0, microsecond=0)
    remainder = candidate.minute % 5
    if remainder:
        candidate += timedelta(minutes=5 - remainder)

    if candidate < now:
        candidate += timedelta(minutes=5)

    return candidate if candidate <= session_close else None


def field_value(output, label):
    pattern = rf"(?mi)^{re.escape(label)}:\s*(.+?)\s*$"
    match = re.search(pattern, output)
    return match.group(1).strip() if match else ""


def paper_trading_status(output):
    lines = output.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip() != "PAPER TRADING":
            continue

        for line in lines[index + 1:index + 20]:
            match = re.match(r"\s*Status:\s*(.+?)\s*$", line)
            if match:
                return match.group(1)
        break

    return ""


def parse_output(output):
    """Extract display values only; raw output remains the source of record."""

    return {
        "spot_price": field_value(output, "NIFTY Spot"),
        "decision": field_value(output, "Decision"),
        "direction": field_value(output, "Direction"),
        "confidence": field_value(output, "Direction Confidence"),
        "evidence_strength": field_value(output, "Evidence Strength"),
        "regime": field_value(output, "Primary Regime"),
        "trend": field_value(output, "Trend"),
        "candle_timestamp": field_value(output, "Candle Timestamp"),
        "candle_age_minutes": field_value(output, "Candle Age"),
        "support": field_value(output, "Support"),
        "resistance": field_value(output, "Resistance"),
        "paper_trading_status": paper_trading_status(output),
    }


def append_summary(summary_path, row):
    write_header = not summary_path.exists() or summary_path.stat().st_size == 0
    with summary_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def record_exception(exception_path, when, message):
    with exception_path.open("a", encoding="utf-8") as file:
        file.write(f"[{when.isoformat()}] {message}\n")


def run_once(root, logs_path, summary_path, exception_path, scheduled_time, timeout):
    started_at = datetime.now(INDIA_TIMEZONE)
    raw_path = logs_path / "raw" / f"{scheduled_time:%H-%M}.txt"
    command = [sys.executable, RUNNER]
    output = ""
    status = "COMPLETED"
    exit_code = ""
    exception = ""

    try:
        completed = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="backslashreplace",
            timeout=timeout,
            check=False,
        )
        output = completed.stdout or ""
        exit_code = completed.returncode
        if completed.returncode != 0:
            status = "FAILED"
            exception = f"Runner exited with code {completed.returncode}."

    except Exception as exc:
        status = "EXCEPTION"
        exception = f"{type(exc).__name__}: {exc}"
        output = traceback.format_exc()

    raw_path.write_text(output, encoding="utf-8", errors="backslashreplace")

    if exception:
        record_exception(exception_path, started_at, exception)

    row = {
        "run_timestamp": started_at.isoformat(),
        "scheduled_time": scheduled_time.strftime("%H:%M"),
        "status": status,
        "exit_code": exit_code,
        "exception": exception,
        "raw_log": raw_path.as_posix(),
        **parse_output(output),
    }
    append_summary(summary_path, row)
    print(f"[{started_at:%H:%M:%S}] {status}: {raw_path}")


def read_summary(summary_path):
    if not summary_path.exists():
        return []
    with summary_path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def generate_report(summary_path, report_path):
    rows = read_summary(summary_path)
    completed = sum(row["status"] == "COMPLETED" for row in rows)
    failed = len(rows) - completed
    decisions = {}
    for row in rows:
        decision = row["decision"] or "UNPARSED"
        decisions[decision] = decisions.get(decision, 0) + 1

    lines = [
        "# Day 1 Live Test Report",
        "",
        f"Generated: {datetime.now(INDIA_TIMEZONE).isoformat()}",
        f"Runs: {len(rows)} | Completed: {completed} | Failed/exception: {failed}",
        "",
        "## Decisions",
        "",
    ]
    lines.extend(f"- {decision}: {count}" for decision, count in sorted(decisions.items()))
    lines.extend([
        "",
        "## Run Summary",
        "",
        "| Slot | Status | Spot | Decision | Direction | Confidence | Regime | Candle age | Paper status | Raw output |",
        "|---|---|---:|---|---|---:|---|---:|---|---|",
    ])
    for row in rows:
        lines.append(
            "| {scheduled_time} | {status} | {spot_price} | {decision} | "
            "{direction} | {confidence} | {regime} | {candle_age_minutes} | "
            "{paper_trading_status} | {raw_log} |".format(**row)
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    arguments = parse_arguments()
    if arguments.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be greater than zero.")

    root = Path(__file__).resolve().parent
    logs_path = root / "logs"
    raw_path = logs_path / "raw"
    raw_path.mkdir(parents=True, exist_ok=True)
    summary_path = logs_path / "day1_summary.csv"
    report_path = logs_path / "day1_report.md"
    exception_path = logs_path / "day1_exceptions.log"

    try:
        if arguments.once:
            run_once(
                root, logs_path, summary_path, exception_path,
                datetime.now(INDIA_TIMEZONE), arguments.timeout_seconds,
            )
            return

        while True:
            slot = next_run_time(datetime.now(INDIA_TIMEZONE))
            if slot is None:
                break

            delay = max(0, (slot - datetime.now(INDIA_TIMEZONE)).total_seconds())
            if delay:
                print(f"Waiting for scheduled run at {slot:%H:%M} IST.")
                time.sleep(delay)

            run_once(
                root, logs_path, summary_path, exception_path,
                slot, arguments.timeout_seconds,
            )

    except KeyboardInterrupt:
        print("Day 1 harness interrupted; generating report from completed runs.")

    finally:
        generate_report(summary_path, report_path)
        print(f"Session report written to {report_path}")


if __name__ == "__main__":
    main()

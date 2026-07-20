"""Manual, read-only command-line entry point for daily research archiving."""

import argparse
import json
import sys

from services.daily_research_report_runner import DailyResearchReportRunner


def _configure_utf8_output():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError, AttributeError):
                pass


def _safe_print(value):
    text = str(value)
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def _print_result(result):
    _safe_print("DAILY RESEARCH REPORT RUNNER")
    _safe_print("Mode: READ ONLY")
    _safe_print("Research Only: True")
    _safe_print("Session Date: {}".format(result.get("session_date")))
    _safe_print("Journal Entries Loaded: {}".format(result.get("journal_entries_loaded")))
    _safe_print("Paper Trades Loaded: {}".format(result.get("paper_trades_loaded")))
    _safe_print("Report Status: {}".format(result.get("report_status")))
    _safe_print("Archive Status: {}".format(result.get("archive_status")))
    if result.get("archive_path"):
        _safe_print("Archive Path: {}".format(result["archive_path"]))
    if result.get("error"):
        _safe_print("Error: {}".format(result["error"]))
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    _safe_print("Research Observations:")
    for observation in report.get("research_observations") or []:
        _safe_print("- {}".format(observation))
    _safe_print("Research Snapshot: {}".format(json.dumps(report.get("research_snapshot") or {}, ensure_ascii=False, sort_keys=True)))
    _safe_print("READ-ONLY MARKET RESEARCH")
    _safe_print("NO REAL ORDER WAS PLACED")


def main(argv=None, *, runner_factory=DailyResearchReportRunner):
    _configure_utf8_output()
    parser = argparse.ArgumentParser(description="Archive a daily read-only research report.")
    parser.add_argument("--date", dest="session_date", default=None, help="Session date in YYYY-MM-DD format.")
    args = parser.parse_args(argv)
    result = runner_factory().run(session_date=args.session_date)
    _print_result(result)
    return 0 if result.get("status") in ("COMPLETED", "COMPLETED_WITH_ERRORS") else 1


if __name__ == "__main__":
    raise SystemExit(main())

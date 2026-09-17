"""CLI for Task 7A complete replay certification."""
from __future__ import annotations

from services.certification.repository_replay_certification_launcher import (
    DEFAULT_REPLAY_REPORT_PATH,
    launch_repository_replay_certification,
)


def main() -> int:
    try:
        report = launch_repository_replay_certification()
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return 2

    print(
        f"{report.overall_status}: "
        f"NIFTY={report.nifty_closed_trades}, "
        f"SENSEX={report.sensex_closed_trades}, "
        f"NO_TRADE={report.no_trade_count}, "
        f"BLOCKED={report.blocked_count}, "
        f"FAILED={report.failed_count}"
    )
    print(f"task_8_ready: {report.task_8_ready}")
    print(f"report: {DEFAULT_REPLAY_REPORT_PATH}")
    return 0 if report.task_8_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())

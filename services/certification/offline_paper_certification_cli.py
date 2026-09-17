"""Command-line entry point for deterministic offline PAPER certification."""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

from services.certification.offline_paper_certification_runner import (
    run_offline_paper_certification,
)


EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_BLOCKED_OR_INVALID = 2


def _aware_datetime(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "generated-at must be ISO-8601"
        ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise argparse.ArgumentTypeError(
            "generated-at must be timezone-aware"
        )
    return result


def _csv_tuple(value: str) -> tuple[str, ...]:
    if not value.strip():
        return ()
    return tuple(
        item.strip()
        for item in value.split(",")
        if item.strip()
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="offline-paper-certification",
        description=(
            "Build a deterministic, network-free, PAPER-only "
            "certification report."
        ),
    )
    parser.add_argument("--report-id", required=True)
    parser.add_argument(
        "--generated-at",
        required=True,
        type=_aware_datetime,
    )
    parser.add_argument("--branch-name", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--failed-check-ids",
        default=(),
        type=_csv_tuple,
    )
    parser.add_argument(
        "--blocked-check-ids",
        default=(),
        type=_csv_tuple,
    )
    parser.add_argument(
        "--warnings",
        default=(),
        type=_csv_tuple,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        report = run_offline_paper_certification(
            report_id=args.report_id,
            generated_at=args.generated_at,
            branch_name=args.branch_name,
            commit_sha=args.commit_sha,
            output_path=args.output,
            failed_check_ids=args.failed_check_ids,
            blocked_check_ids=args.blocked_check_ids,
            additional_warnings=args.warnings,
        )
    except SystemExit as exc:
        return int(exc.code)
    except (TypeError, ValueError, OSError) as exc:
        print(
            f"offline PAPER certification failed: {exc}",
            file=sys.stderr,
        )
        return EXIT_BLOCKED_OR_INVALID

    print(
        f"{report.overall_status}: "
        f"{report.passed_count} passed, "
        f"{report.failed_count} failed, "
        f"{report.blocked_count} blocked"
    )
    print(f"report: {args.output}")

    if report.overall_status == "PASSED":
        return EXIT_PASSED
    if report.overall_status == "FAILED":
        return EXIT_FAILED
    return EXIT_BLOCKED_OR_INVALID


if __name__ == "__main__":
    raise SystemExit(main())

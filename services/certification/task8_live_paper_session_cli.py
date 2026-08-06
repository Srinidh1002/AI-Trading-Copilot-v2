"""CLI for bounded Task 8 live PAPER certification sessions."""
from __future__ import annotations

import argparse
import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from services.certification.task8_live_paper_session import (
    run_task8_live_paper_session,
)


DEFAULT_FACTORY = (
    "services.certification."
    "task8_live_paper_default_composition:"
    "build_task8_dependencies"
)


def _load(path: str):
    module_name, separator, attribute_name = path.partition(
        ":"
    )
    if not separator:
        raise ValueError(
            "factory must use module:function syntax"
        )

    module = importlib.import_module(module_name)
    factory = getattr(module, attribute_name)

    if not callable(factory):
        raise TypeError("factory must be callable")

    return factory


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_session_id() -> str:
    timestamp = _utc_now().strftime("%Y%m%dT%H%M%S%fZ")
    return (
        f"task8-session-{timestamp}-"
        f"{uuid4().hex[:8]}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bounded multi-cycle Task 8 live-read "
            "PAPER certification session"
        )
    )
    parser.add_argument(
        "--factory",
        default=DEFAULT_FACTORY,
        help=(
            "module:function returning "
            "Task8CanaryDependenciesV1"
        ),
    )
    parser.add_argument(
        "--cycle-count",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=60.0,
    )
    parser.add_argument(
        "--output-directory",
        default="artifacts/certification/task8/session",
    )
    parser.add_argument(
        "--session-id",
        default=None,
    )
    args = parser.parse_args(argv)

    try:
        dependency_factory = _load(args.factory)
        session_id = (
            args.session_id
            if args.session_id
            else _default_session_id()
        )

        report, path = run_task8_live_paper_session(
            dependency_factory=dependency_factory,
            cycle_count=args.cycle_count,
            interval_seconds=args.interval_seconds,
            output_directory=Path(
                args.output_directory
            ),
            clock=_utc_now,
            session_id_factory=lambda: session_id,
        )

        print(report.to_json())
        print(
            "Task 8 session: "
            f"{report.session_status}; "
            f"completed={report.completed_cycle_count}/"
            f"{report.requested_cycle_count}; "
            f"evidence={path}",
            file=sys.stderr,
        )

        return 0 if report.passed else 1

    except Exception as exc:
        print(
            "Task 8 session execution/configuration "
            f"exception: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

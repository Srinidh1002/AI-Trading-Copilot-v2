"""CLI for one Task 8 live-read PAPER canary."""
from __future__ import annotations

import argparse
import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from services.certification.task8_canary_failure_evidence import (
    build_task8_canary_failure_report,
    write_task8_canary_failure_report,
)
from services.certification.task8_live_paper_canary import (
    Task8CanaryDependenciesV1,
    run_task8_live_paper_canary,
    write_task8_report,
)


DEFAULT_FACTORY = (
    "services.certification."
    "task8_live_paper_default_composition:"
    "build_task8_dependencies"
)


def _load(path: str):
    module_name, separator, attribute_name = (
        path.partition(":")
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


def _failure_run_id() -> str:
    timestamp = _utc_now().strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    return (
        f"task8-live-failure-{timestamp}-"
        f"{uuid4().hex[:8]}"
    )


def _default_output(run_id: str) -> Path:
    return (
        Path("artifacts/certification/task8")
        / f"{run_id}.json"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Task 8 live-read PAPER canary"
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
        "--output",
        default=None,
    )
    args = parser.parse_args(argv)

    requested_at = _utc_now()
    fallback_run_id = _failure_run_id()

    try:
        dependencies = _load(args.factory)()

        if type(dependencies) is not Task8CanaryDependenciesV1:
            raise TypeError(
                "factory must return exact "
                "Task8CanaryDependenciesV1"
            )

        report = run_task8_live_paper_canary(
            dependencies
        )

        output = (
            Path(args.output)
            if args.output
            else _default_output(report.run_id)
        )

        path = write_task8_report(
            report,
            output,
        )

        print(report.to_json())
        print(
            "Task 8 canary: "
            f"{report.outer_status}; "
            f"evidence={path}",
            file=sys.stderr,
        )

        return 0 if report.passed else 1

    except Exception as exc:
        completed_at = _utc_now()

        failure_report = (
            build_task8_canary_failure_report(
                run_id=fallback_run_id,
                requested_at=requested_at,
                completed_at=completed_at,
                exception=exc,
            )
        )

        output = (
            Path(args.output)
            if args.output
            else _default_output(
                failure_report.run_id
            )
        )

        try:
            path = write_task8_canary_failure_report(
                failure_report,
                output,
            )
        except Exception as write_exc:
            print(
                "Task 8 canary failure-evidence "
                f"write exception: "
                f"{type(write_exc).__name__}",
                file=sys.stderr,
            )
            return 2

        print(failure_report.to_json())
        print(
            "Task 8 canary: FAILED; "
            "countable=false; "
            f"provider_throttled="
            f"{str(failure_report.provider_throttled).lower()}; "
            f"evidence={path}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the deterministic provider-free Task 2 certification matrix."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.certification.task2_decision_certification_matrix import (
    run_all_task2_decision_certification_scenarios,
    run_task2_decision_certification_scenario,
)


DEFAULT_OUTPUT = Path(
    "artifacts/certification/task2/"
    "task2_decision_certification.json"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run provider-free deterministic Task 2 decision certification."
        )
    )
    parser.add_argument(
        "--scenario",
        help="Run one canonical Task 2 certification scenario.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the JSON report to this path.",
    )
    return parser


def _write_json_atomic(output: Path, payload: str) -> None:
    """Write a report without leaving a partially written final file."""

    output.parent.mkdir(parents=True, exist_ok=True)

    temporary = output.with_name(f"{output.name}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(output)


def _status(result: Any) -> str:
    return getattr(
        result,
        "overall_status",
        getattr(result, "certification_status", "FAILED"),
    )


def _print_summary(result: Any, output: Path) -> None:
    status = _status(result)

    if hasattr(result, "total_scenarios"):
        print(
            "Task 2 certification: "
            f"{status}; "
            f"total={result.total_scenarios}; "
            f"passed={result.passed_scenarios}; "
            f"failed={result.failed_scenarios}; "
            f"output={output}"
        )
        return

    print(
        "Task 2 certification: "
        f"{status}; "
        f"scenario={result.scenario_id}; "
        f"selected_market={result.selected_market}; "
        f"parent_action={result.parent_action}; "
        f"output={output}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.scenario:
            result = run_task2_decision_certification_scenario(
                args.scenario
            )
        else:
            result = (
                run_all_task2_decision_certification_scenarios()
            )
    except ValueError as exc:
        code = str(exc)

        if code == "UNKNOWN_SCENARIO":
            print("Task 2 certification error: UNKNOWN_SCENARIO", file=sys.stderr)
            return 2

        print(
            "Task 2 certification error: CERTIFICATION_INPUT_INVALID",
            file=sys.stderr,
        )
        return 2

    output = args.output or DEFAULT_OUTPUT

    try:
        _write_json_atomic(output, result.to_json())
    except (OSError, ValueError):
        print(
            "Task 2 certification error: REPORT_WRITE_FAILED",
            file=sys.stderr,
        )
        return 3

    _print_summary(result, output)

    return 0 if _status(result) == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
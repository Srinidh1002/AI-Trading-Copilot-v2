from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from services.certification.task8_live_paper_canary import (
    Task8CanaryDependenciesV1, run_task8_live_paper_canary, write_task8_report,
)


def _load(path: str):
    module, separator, name = path.partition(":")
    if not separator:
        raise ValueError("factory must use module:function syntax")
    factory = getattr(importlib.import_module(module), name)
    if not callable(factory):
        raise TypeError("factory must be callable")
    return factory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task 8 live-read PAPER canary")
    parser.add_argument("--factory", default="services.certification.task8_live_paper_default_composition:build_task8_dependencies", help="module:function returning Task8CanaryDependenciesV1")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    try:
        dependencies = _load(args.factory)()
        if type(dependencies) is not Task8CanaryDependenciesV1:
            raise TypeError("factory must return exact Task8CanaryDependenciesV1")
        report = run_task8_live_paper_canary(dependencies)
        output = Path(args.output) if args.output else Path("artifacts/certification/task8") / f"{report.run_id}.json"
        path = write_task8_report(report, output)
        print(report.to_json())
        print(f"Task 8 canary: {report.outer_status}; evidence={path}", file=sys.stderr)
        return 0 if report.passed else 1
    except Exception as exc:
        print(f"Task 8 canary execution/configuration exception: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import importlib
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
    parser.add_argument("--factory", required=True, help="module:function returning Task8CanaryDependenciesV1")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        dependencies = _load(args.factory)()
        if type(dependencies) is not Task8CanaryDependenciesV1:
            raise TypeError("factory must return exact Task8CanaryDependenciesV1")
        report = run_task8_live_paper_canary(dependencies)
        path = write_task8_report(report, Path(args.output))
        print(f"Task 8 canary: {report.outer_status}; selected={report.selected_market}; blockers={len(report.pass_blockers)}")
        print(f"Evidence: {path}")
        return 0 if report.passed else 1
    except Exception as exc:
        print(f"Task 8 canary execution/configuration exception: {type(exc).__name__}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

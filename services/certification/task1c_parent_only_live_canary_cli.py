from __future__ import annotations
import argparse, sys
from datetime import datetime, timezone
from pathlib import Path
from services.certification.task1c_parent_only_default_composition import build_task1c_parent_only_dependencies
from services.certification.task1c_parent_only_live_canary import run_task1c_parent_only_live_canary, write_task1c_parent_only_report

def _safe_failure(exc: Exception, *, stage: str) -> tuple[str, str]:
    """Never surface raw provider or credential-bearing exception text."""
    name = type(exc).__name__
    if stage == "DEPENDENCY_CONSTRUCTION": return ("DEPENDENCY_CONSTRUCTION_FAILED", name)
    if isinstance(exc, ValueError): return ("PARENT_EVALUATION_FAILED", "VALIDATION_VALUE_ERROR")
    if isinstance(exc, RuntimeError): return ("PARENT_EVALUATION_FAILED", "RUNTIME_EVIDENCE_UNAVAILABLE")
    return ("PARENT_EVALUATION_FAILED", f"UNEXPECTED_{name.upper()}")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task 1C parent-only live-read canary")
    parser.add_argument("--confirm-live-read", action="store_true", help="required before any live provider read")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    if not args.confirm_live_read:
        print("Refusing live read: pass --confirm-live-read.", file=sys.stderr); return 2
    try:
        try:
            dependencies = build_task1c_parent_only_dependencies()
        except Exception as exc:
            code, reason = _safe_failure(exc, stage="DEPENDENCY_CONSTRUCTION")
            print(f"Task 1C parent-only canary failed: stage={code} reason={reason} exception={type(exc).__name__}", file=sys.stderr); return 1
        report = run_task1c_parent_only_live_canary(dependencies)
        output = Path(args.output) if args.output else Path("artifacts/canary") / f"task1c-parent-only-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
        path = write_task1c_parent_only_report(report, output)
        print(f"Task 1C parent-only: {report.parent_action}; selected={report.selected_market}; evidence={path}")
        return 0
    except Exception as exc:
        code, reason = _safe_failure(exc, stage="PARENT_EVALUATION")
        substage = dependencies.last_substage() if "dependencies" in locals() else "DEPENDENCY_READY"
        print(f"Task 1C parent-only canary failed: stage={code} substage={substage} reason={reason} exception={type(exc).__name__}", file=sys.stderr); return 1

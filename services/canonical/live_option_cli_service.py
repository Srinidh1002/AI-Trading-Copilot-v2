"""Explicit canonical CLI operations; no operation chains into execution."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from services.canonical.comparison import compare_dashboard_legacy_to_canonical
from services.contracts.final_decision_v1 import FinalDecisionV1
from services.contracts.market_snapshot_v1 import from_dashboard_snapshot
from services.contracts.paper_trade_candidate_v1 import PaperTradeCandidateV1
from services.paper import execute_paper_candidate, prepare_paper_candidate

from .pipeline import run_canonical_pipeline


def configured_cli_analysis_mode(value: str | None = None) -> str:
    mode = str(value or os.getenv("CLI_ANALYSIS_MODE", "canonical")).strip().lower()
    return mode if mode in {"canonical", "legacy", "compare"} else "canonical"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canonical live-option analysis")
    parser.add_argument(
        "operation",
        nargs="?",
        default="analyse",
        choices=("analyse", "prepare-paper", "execute-paper"),
    )
    parser.add_argument("--mode", choices=("canonical", "legacy", "compare"))
    parser.add_argument("--snapshot-file")
    parser.add_argument(
        "--underlying",
        help="Accepted for CLI compatibility; supplied artifacts own identity.",
    )
    parser.add_argument("--decision-file")
    parser.add_argument("--candidate-file")
    parser.add_argument("--approve", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    mode = configured_cli_analysis_mode(args.mode)

    if args.operation == "analyse":
        return _analyse(args.snapshot_file, mode)
    if args.operation == "prepare-paper":
        return _prepare(args.snapshot_file, args.decision_file)
    return _execute(args.candidate_file, args.decision_file, args.approve)


def _analyse(snapshot_file: str | None, mode: str) -> int:
    snapshot_payload = _load_snapshot(snapshot_file)
    if snapshot_payload is None:
        return _print_error("A --snapshot-file is required for analysis.", code=2)

    try:
        if mode == "legacy":
            from services.trade.trade_engine import analyze_trade

            result = analyze_trade(snapshot_payload)
            print(json.dumps(result, sort_keys=True, default=str))
            return 0

        if mode == "compare":
            from services.trade.trade_engine import analyze_trade

            legacy_result = analyze_trade(snapshot_payload)
            comparison = compare_dashboard_legacy_to_canonical(
                snapshot_payload,
                legacy_result,
            )
            print(comparison.to_json())
            return 0

        snapshot = from_dashboard_snapshot(snapshot_payload)
        decision = run_canonical_pipeline(snapshot)
        print(decision.to_json())
        return 0

    except Exception as exc:
        return _print_error(
            f"{mode.title()} analysis failed: {type(exc).__name__}.",
            code=2,
        )


def _prepare(snapshot_file: str | None, decision_file: str | None) -> int:
    try:
        decision = _load_decision(decision_file)

        if decision is None and snapshot_file:
            payload = _load_snapshot(snapshot_file)
            if payload is not None:
                decision = run_canonical_pipeline(from_dashboard_snapshot(payload))

        if decision is None:
            return _print_error(
                "A canonical --decision-file or --snapshot-file is required.",
                code=2,
            )

        preparation = prepare_paper_candidate(decision)
        print(
            json.dumps(
                {
                    "status": preparation.status,
                    "candidate": (
                        preparation.candidate.to_dict()
                        if preparation.candidate is not None
                        else None
                    ),
                    "errors": list(preparation.errors),
                    "warnings": list(preparation.warnings),
                },
                sort_keys=True,
            )
        )
        return 0

    except Exception as exc:
        return _print_error(
            f"Paper candidate preparation failed: {type(exc).__name__}.",
            code=2,
        )


def _execute(
    candidate_file: str | None,
    decision_file: str | None,
    approved: bool,
) -> int:
    candidate_payload = _load_json(candidate_file)
    decision = _load_decision(decision_file)

    if not isinstance(candidate_payload, Mapping) or decision is None:
        return _print_error(
            "Both --candidate-file and --decision-file are required.",
            code=2,
        )

    try:
        candidate = PaperTradeCandidateV1.from_dict(candidate_payload)
    except Exception as exc:
        return _print_error(
            f"Invalid paper candidate: {type(exc).__name__}.",
            code=2,
        )

    try:
        timezone = candidate.created_at.tzinfo
        if timezone is None:
            return _print_error(
                "Paper candidate created_at must be timezone-aware.",
                code=2,
            )

        result = execute_paper_candidate(
            candidate,
            decision,
            approved=approved,
            now=datetime.now(timezone),
        )
    except Exception as exc:
        return _print_error(
            f"Paper execution boundary failed: {type(exc).__name__}.",
            code=2,
        )

    print(
        json.dumps(
            {
                "submitted": result.submitted,
                "status": result.status,
                "reason": result.reason,
            },
            sort_keys=True,
        )
    )
    return 0 if result.submitted else 1


def _load_snapshot(path: str | None) -> Mapping[str, Any] | None:
    payload = _load_json(path)
    return payload if isinstance(payload, Mapping) else None


def _load_decision(path: str | None) -> FinalDecisionV1 | None:
    payload = _load_json(path)
    if not isinstance(payload, Mapping):
        return None

    try:
        return FinalDecisionV1.from_dict(payload)
    except Exception:
        return None


def _load_json(path: str | None) -> Any:
    if not path:
        return None

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _print_error(message: str, *, code: int) -> int:
    print(json.dumps({"error": message}, sort_keys=True))
    return code

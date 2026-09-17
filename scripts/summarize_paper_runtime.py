"""Read-only summarizer for certified automated PAPER runtime evidence.

The utility accepts a runtime JSONL file plus optional deterministic journal and
persistence documents.  It never imports or constructs the runtime and only
opens evidence files for reading.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_INPUT = Path("data/paper_trading/certified_runtime/runtime.jsonl")
_INNER_STATUS = re.compile(r"cycle_status='([A-Z_]+)'")
_ACTION = re.compile(r"'(ENTRY(?:_[A-Z]+)?|PARTIAL_EXIT(?:_[A-Z]+)?|STOP_EXIT(?:_[A-Z]+)?|TARGET(?:_[0-9]+)?_EXIT(?:_[A-Z]+)?)'")
_MARKET = re.compile(r"(?:underlying_symbol|market)='(NIFTY|SENSEX)'")
_SELECTED_MARKET = re.compile(r"selected_market(?:_key)?[=:]'?(NIFTY|SENSEX)")


def _counter_dict(counter: Counter) -> dict[str, int]:
    return {str(key): counter[key] for key in sorted(counter)}


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    if not path.exists():
        issues.append({"code": "INPUT_MISSING", "path": str(path)})
        return records, issues
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    value = json.loads(text)
                except json.JSONDecodeError as exc:
                    issues.append(
                        {
                            "code": "MALFORMED_JSONL",
                            "line_number": line_number,
                            "message": str(exc),
                            "path": str(path),
                        }
                    )
                    continue
                if not isinstance(value, dict):
                    issues.append(
                        {
                            "code": "NON_OBJECT_JSONL_RECORD",
                            "line_number": line_number,
                            "path": str(path),
                        }
                    )
                    continue
                records.append(value)
    except OSError as exc:
        issues.append({"code": "INPUT_READ_ERROR", "message": str(exc), "path": str(path)})
    return records, issues


def _read_json_document(path: Path) -> tuple[Any | None, dict[str, Any] | None]:
    if not path.exists():
        return None, None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, {"code": "OPTIONAL_DOCUMENT_UNREADABLE", "message": str(exc), "path": str(path)}


def _walk(value: Any) -> Iterable[tuple[str | None, Any]]:
    if isinstance(value, Mapping):
        for key in sorted(value, key=str):
            item = value[key]
            yield str(key), item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield None, item
            yield from _walk(item)


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    for _, child in _walk(value):
        if isinstance(child, str):
            yield child


def _extract_actions(value: Any) -> Counter:
    actions: Counter = Counter()
    for key, child in _walk(value):
        if key == "paper_actions" and isinstance(child, list):
            for action in child:
                if isinstance(action, str):
                    actions[action.upper()] += 1
    for text in _strings(value):
        for action in _ACTION.findall(text):
            actions[action] += 1
    return actions


def _inner_statuses(value: Any) -> Counter:
    statuses: Counter = Counter()
    for key, child in _walk(value):
        if key == "cycle_status" and isinstance(child, str):
            statuses[child.upper()] += 1
    for text in _strings(value):
        statuses.update(_INNER_STATUS.findall(text))
    return statuses


def _market_statuses(value: Any) -> Counter:
    markets: Counter = Counter()
    for key, child in _walk(value):
        if key in {"underlying_symbol", "market", "selected_market"} and isinstance(child, str):
            name = child.strip().upper()
            if name in {"NIFTY", "SENSEX"}:
                markets[name] += 1
    for text in _strings(value):
        markets.update(_MARKET.findall(text))
    return markets


def _selected_markets(value: Any) -> Counter:
    selected: Counter = Counter()
    for key, child in _walk(value):
        if key in {"selected_market", "selected_market_key"} and isinstance(child, str):
            name = child.strip().upper()
            if name in {"NIFTY", "SENSEX"}:
                selected[name] += 1
    for text in _strings(value):
        selected.update(_SELECTED_MARKET.findall(text))
    return selected


def _classify_actions(actions: Counter) -> dict[str, int]:
    def count(prefix: str) -> int:
        return sum(number for action, number in actions.items() if action.startswith(prefix))

    return {
        "entries": count("ENTRY"),
        "partial_exits": count("PARTIAL_EXIT"),
        "stop_exits": count("STOP_EXIT"),
        "target_exits": count("TARGET"),
    }


def _optional_paths(input_path: Path, supplied: Iterable[Path]) -> list[Path]:
    candidates = list(supplied)
    root = input_path.parent
    for name in (
        "opportunity_orchestration_journal.json",
        "monitoring_orchestration_journal.json",
        "p7_trades.json",
        "p8_portfolios.json",
    ):
        candidate = root / name
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def summarize(
    input_path: str | Path = DEFAULT_INPUT,
    *,
    evidence_paths: Iterable[str | Path] = (),
) -> dict[str, Any]:
    """Return a deterministic report without mutating any evidence file."""
    runtime_path = Path(input_path)
    records, issues = _read_jsonl(runtime_path)
    events = Counter()
    outer_statuses = {"opportunity": Counter(), "monitoring": Counter()}
    inner_statuses = {"opportunity": Counter(), "monitoring": Counter()}
    actions: Counter = Counter()
    markets = Counter()
    selected_markets = Counter()
    starts: list[dict[str, Any]] = []
    stops: list[dict[str, Any]] = []
    startup_statuses = Counter()
    cycle_totals = Counter()
    duplicate_evidence = Counter()
    reservations = Counter()
    source_files: list[dict[str, Any]] = [{"kind": "runtime_jsonl", "path": str(runtime_path), "records": len(records)}]

    for record in records:
        event = str(record.get("event", "UNKNOWN")).upper()
        events[event] += 1
        if event == "RUNTIME_STARTING":
            starts.append(record)
        elif event in {"RUNTIME_STOPPED", "RUNTIME_INTERRUPTED", "RUNTIME_FAILED"}:
            stops.append(record)

        stats = record.get("stats")
        if isinstance(stats, Mapping):
            for field in ("cycles_started", "cycles_completed", "cycles_with_errors"):
                if isinstance(stats.get(field), int):
                    cycle_totals[field] += stats[field]
            startup_status = stats.get("startup_status")
            if isinstance(startup_status, str):
                startup_statuses[startup_status.upper()] += 1
            last_cycle = stats.get("last_cycle")
            if isinstance(last_cycle, Mapping):
                for operation in ("opportunity", "monitoring"):
                    item = last_cycle.get(operation)
                    if not isinstance(item, Mapping):
                        continue
                    outer = item.get("status")
                    if isinstance(outer, str):
                        outer_statuses[operation][outer.upper()] += 1
                    result = item.get("result")
                    inner_statuses[operation].update(_inner_statuses(result))
                    text = " ".join(_strings(result))
                    if "no active certified P7 position is available for monitoring" in text:
                        duplicate_evidence["NO_ACTIVE_POSITION_FAIL_CLOSED"] += 1
                    if "DUPLICATE_SAME_PAYLOAD" in text:
                        duplicate_evidence["DUPLICATE_SAME_PAYLOAD"] += 1
                    if "IDEMPOTENCY_PAYLOAD_CONFLICT" in text:
                        duplicate_evidence["IDEMPOTENCY_PAYLOAD_CONFLICT"] += 1

        actions.update(_extract_actions(record))
        markets.update(_market_statuses(record))
        selected_markets.update(_selected_markets(record))

    for path in _optional_paths(runtime_path, (Path(item) for item in evidence_paths)):
        document, issue = _read_json_document(path)
        if issue is not None:
            issues.append(issue)
            continue
        if document is None:
            continue
        source_files.append({"kind": "optional_json", "path": str(path)})
        actions.update(_extract_actions(document))
        markets.update(_market_statuses(document))
        selected_markets.update(_selected_markets(document))
        for key, child in _walk(document):
            if key == "reservation_status" and isinstance(child, str):
                reservations[child.upper()] += 1
            if key == "duplicate_of_cycle_result_id" and child:
                duplicate_evidence["DUPLICATE_OF_CYCLE_RESULT"] += 1
        for text in _strings(document):
            if "DUPLICATE_SAME_PAYLOAD" in text:
                duplicate_evidence["DUPLICATE_SAME_PAYLOAD"] += 1
            if "IDEMPOTENCY_PAYLOAD_CONFLICT" in text:
                duplicate_evidence["IDEMPOTENCY_PAYLOAD_CONFLICT"] += 1

    inner_failed = sum(value for status, value in inner_statuses["opportunity"].items() if status == "FAILED") + sum(value for status, value in inner_statuses["monitoring"].items() if status == "FAILED")
    assessment = "INNER_FAILURE_OR_FAIL_CLOSED_PRESENT" if inner_failed or duplicate_evidence["NO_ACTIVE_POSITION_FAIL_CLOSED"] else "NO_INNER_FAILURE_OBSERVED"
    return {
        "assessment": assessment,
        "capital": {
            "reservation_statuses": _counter_dict(reservations),
            "reservations_observed": sum(reservations.values()),
            "releases_observed": reservations.get("RELEASED", 0),
        },
        "cycles": {
            "completed": cycle_totals["cycles_completed"],
            "monitoring_invocations": sum(outer_statuses["monitoring"].values()),
            "opportunity_invocations": sum(outer_statuses["opportunity"].values()),
            "outer_monitoring_statuses": _counter_dict(outer_statuses["monitoring"]),
            "outer_opportunity_statuses": _counter_dict(outer_statuses["opportunity"]),
            "outer_cycle_errors": cycle_totals["cycles_with_errors"],
            "requested": sum(start.get("max_cycles", 0) for start in starts if isinstance(start.get("max_cycles"), int)),
            "started": cycle_totals["cycles_started"],
        },
        "duplicate_prevention_evidence": _counter_dict(duplicate_evidence),
        "inner": {
            "monitoring_statuses": _counter_dict(inner_statuses["monitoring"]),
            "opportunity_statuses": _counter_dict(inner_statuses["opportunity"]),
        },
        "market_evidence": {
            "nifty_observations": markets["NIFTY"],
            "selected_market": _counter_dict(selected_markets),
            "sensex_observations": markets["SENSEX"],
        },
        "paper_actions": {**_classify_actions(actions), "all_actions": _counter_dict(actions)},
        "runtime": {
            "automated_paper": _counter_dict(Counter(str(item.get("automated_paper")) for item in starts if "automated_paper" in item)),
            "broker_order_submission": _counter_dict(Counter(str(item.get("broker_order_submission")) for item in starts if "broker_order_submission" in item)),
            "emergency_halt": _counter_dict(Counter(str(item.get("emergency_halt")) for item in starts if "emergency_halt" in item)),
            "events": _counter_dict(events),
            "execution_mode": _counter_dict(Counter(str(item.get("execution_mode")) for item in records if "execution_mode" in item)),
            "graceful_shutdown": _counter_dict(Counter(str(item.get("graceful_shutdown")) for item in stops if "graceful_shutdown" in item)),
            "interrupted": sum(1 for item in stops if str(item.get("event", "")).upper() == "RUNTIME_INTERRUPTED"),
            "live_execution_eligible": _counter_dict(Counter(str(item.get("live_execution_eligible")) for item in records if "live_execution_eligible" in item)),
            "monitoring_authority_enabled": _counter_dict(Counter(str(item.get("position_monitoring_allowed")) for item in starts if "position_monitoring_allowed" in item)),
            "observe_only": _counter_dict(Counter(str(item.get("observe_only")) for item in starts if "observe_only" in item)),
            "opportunity_authority_enabled": _counter_dict(Counter(str(item.get("new_entries_allowed")) for item in starts if "new_entries_allowed" in item)),
            "runtime_starts": len(starts),
            "runtime_stops": len(stops),
        },
        "schema_version": "paper_runtime_summary.v1",
        "source_files": sorted(source_files, key=lambda item: (item["kind"], item["path"])),
        "startup_recovery": _counter_dict(startup_statuses),
        "warnings": sorted(issues, key=lambda item: (item.get("path", ""), item.get("line_number", 0), item["code"])),
    }


def render_text(report: Mapping[str, Any]) -> str:
    """Render a deterministic human-readable view of a summary."""
    lines = ["Certified PAPER Runtime Summary", f"Assessment: {report['assessment']}"]
    for section in ("runtime", "cycles", "inner", "paper_actions", "capital", "market_evidence", "duplicate_prevention_evidence", "startup_recovery"):
        lines.append("")
        lines.append(section.replace("_", " ").title())
        for key, value in sorted(report[section].items()):
            lines.append(f"- {key}: {json.dumps(value, sort_keys=True, separators=(',', ':'))}")
    lines.append("")
    lines.append(f"Warnings: {len(report['warnings'])}")
    return "\n".join(lines) + "\n"


def _write_text(path: str, text: str) -> None:
    if path == "-":
        sys.stdout.write(text)
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only certified PAPER runtime evidence summary")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="runtime.jsonl input path")
    parser.add_argument("--output", required=True, help="stable JSON output path, or - for stdout")
    parser.add_argument("--text-output", default="-", help="human-readable output path, or - for stdout")
    parser.add_argument("--evidence", action="append", default=[], help="optional journal/P7/P8 JSON path; repeatable")
    args = parser.parse_args(argv)
    if args.output == "-" and args.text_output == "-":
        parser.error("--output and --text-output cannot both be -")
    report = summarize(args.input, evidence_paths=args.evidence)
    _write_text(args.output, json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
    _write_text(args.text_output, render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "summarize_paper_runtime.py"
SPEC = importlib.util.spec_from_file_location("summarize_paper_runtime", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _write_jsonl(path, records):
    path.write_text("\n".join(records) + "\n", encoding="utf-8")


def test_summary_distinguishes_outer_completion_from_inner_monitoring_failure(tmp_path):
    runtime = tmp_path / "runtime.jsonl"
    _write_jsonl(
        runtime,
        [
            json.dumps({"event": "RUNTIME_STARTING", "occurred_at": "2026-01-08T10:00:00+00:00", "execution_mode": "PAPER", "live_execution_eligible": False, "automated_paper": True, "observe_only": False, "broker_order_submission": False, "emergency_halt": False, "new_entries_allowed": True, "position_monitoring_allowed": True, "max_cycles": 1}),
            "{not-json}",
            json.dumps({"event": "RUNTIME_STOPPED", "occurred_at": "2026-01-08T10:01:00+00:00", "execution_mode": "PAPER", "live_execution_eligible": False, "graceful_shutdown": True, "stats": {"cycles_started": 1, "cycles_completed": 1, "cycles_with_errors": 0, "startup_status": "COMPLETED", "last_cycle": {"opportunity": {"name": "OPPORTUNITY", "status": "COMPLETED", "result": "cycle_status='COMPLETED_NO_ACTION' underlying_symbol='NIFTY'"}, "monitoring": {"name": "MONITORING", "status": "COMPLETED", "result": "cycle_status='FAILED' errors=('P7_MONITORING_FAILURE',) message='no active certified P7 position is available for monitoring'"}}}}),
        ],
    )

    report = MODULE.summarize(runtime)

    assert report["assessment"] == "INNER_FAILURE_OR_FAIL_CLOSED_PRESENT"
    assert report["cycles"]["outer_monitoring_statuses"] == {"COMPLETED": 1}
    assert report["inner"]["monitoring_statuses"] == {"FAILED": 1}
    assert report["duplicate_prevention_evidence"]["NO_ACTIVE_POSITION_FAIL_CLOSED"] == 1
    assert report["market_evidence"]["nifty_observations"] == 1
    assert report["warnings"][0]["code"] == "MALFORMED_JSONL"


def test_summary_consumes_safe_optional_journal_and_persistence_evidence(tmp_path):
    runtime = tmp_path / "runtime.jsonl"
    journal = tmp_path / "opportunity_orchestration_journal.json"
    portfolio = tmp_path / "p8_portfolios.json"
    _write_jsonl(runtime, [json.dumps({"event": "RUNTIME_STOPPED", "execution_mode": "PAPER", "live_execution_eligible": False, "stats": {"cycles_started": 0, "cycles_completed": 0, "cycles_with_errors": 0}})])
    journal.write_text(json.dumps({"version": 1, "records": {"key": {"duplicate_of_cycle_result_id": "prior", "paper_actions": ["ENTRY_OPEN", "TARGET_1_EXIT"], "selected_market": "SENSEX"}}}), encoding="utf-8")
    portfolio.write_text(json.dumps({"reservations": [{"reservation_status": "RELEASED"}, {"reservation_status": "ACTIVE"}]}), encoding="utf-8")

    report = MODULE.summarize(runtime, evidence_paths=[journal, portfolio])

    assert report["paper_actions"]["entries"] == 1
    assert report["paper_actions"]["target_exits"] == 1
    assert report["capital"]["reservations_observed"] == 2
    assert report["capital"]["releases_observed"] == 1
    assert report["duplicate_prevention_evidence"]["DUPLICATE_OF_CYCLE_RESULT"] == 1
    assert report["market_evidence"]["selected_market"] == {"SENSEX": 1}


def test_summary_and_text_are_deterministic_and_cli_writes_requested_outputs_only(tmp_path):
    runtime = tmp_path / "runtime.jsonl"
    json_output = tmp_path / "summary.json"
    text_output = tmp_path / "summary.txt"
    _write_jsonl(runtime, [json.dumps({"event": "RUNTIME_STARTING", "execution_mode": "PAPER", "live_execution_eligible": False, "automated_paper": False, "observe_only": True, "broker_order_submission": False, "emergency_halt": False, "new_entries_allowed": False, "position_monitoring_allowed": True, "max_cycles": 0})])

    first = MODULE.summarize(runtime)
    second = MODULE.summarize(runtime)
    assert first == second
    assert MODULE.render_text(first) == MODULE.render_text(second)

    assert MODULE.main(["--input", str(runtime), "--output", str(json_output), "--text-output", str(text_output)]) == 0
    assert json.loads(json_output.read_text(encoding="utf-8")) == first
    assert text_output.read_text(encoding="utf-8") == MODULE.render_text(first)

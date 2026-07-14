"""Behavioural tests for read-only daily research orchestration."""

from copy import deepcopy
from datetime import date, datetime
import importlib
from pathlib import Path

import pytest

from services.daily_research_report_runner import DailyResearchReportRunner


class Journal:
    def __init__(self, entries=None, error=None): self.entries, self.error, self.calls = entries or [], error, []
    def read_entries(self, session_date):
        self.calls.append(session_date)
        if self.error: raise self.error
        return deepcopy(self.entries)


class Repository:
    def __init__(self, trades=None, error=None): self.trades, self.error, self.calls = trades or [], error, 0
    def get_all_trades(self):
        self.calls += 1
        if self.error: raise self.error
        return deepcopy(self.trades)


class Builder:
    def __init__(self, result=None, error=None): self.result, self.error, self.calls = result, error, []
    def build_report(self, entries, *, trades=None, session_date=None):
        self.calls.append((deepcopy(entries), deepcopy(trades), session_date))
        if self.error: raise self.error
        return deepcopy(self.result if self.result is not None else report(session_date))


class Archive:
    def __init__(self, result=None, error=None): self.result, self.error, self.calls = result, error, []
    def save_report(self, value):
        self.calls.append(deepcopy(value))
        if self.error: raise self.error
        return deepcopy(self.result if self.result is not None else {"status": "SAVED", "success": True, "path": "/archive/report.json"})


def entry(day="2026-07-15", value=1): return {"session_date": day, "value": value}
def report(day="2026-07-15", status="COMPLETED"): return {"status": status, "read_only": True, "research_only": True, "session_date": day, "research_observations": ["Observed ₹"], "research_snapshot": {"final_decision": "WAIT"}}


def make_runner(*, journal=None, repository=None, builder=None, archive=None):
    return DailyResearchReportRunner(market_cycle_journal=journal or Journal(), paper_trade_repository=repository or Repository(), daily_research_report=builder or Builder(), research_report_archive=archive or Archive())


def test_default_dependencies_construct():
    runner = DailyResearchReportRunner()
    assert runner.market_cycle_journal and runner.paper_trade_repository and runner.daily_research_report and runner.research_report_archive


@pytest.mark.parametrize("name", ["market_cycle_journal", "paper_trade_repository", "daily_research_report", "research_report_archive"])
def test_injected_dependencies_are_accepted(name):
    values = {"market_cycle_journal": Journal(), "paper_trade_repository": Repository(), "daily_research_report": Builder(), "research_report_archive": Archive()}
    runner = DailyResearchReportRunner(**values)
    assert getattr(runner, name) is values[name]


def test_construction_does_not_run_dependencies():
    journal, repository, builder, archive = Journal(), Repository(), Builder(), Archive()
    make_runner(journal=journal, repository=repository, builder=builder, archive=archive)
    assert journal.calls == [] and repository.calls == 0 and builder.calls == [] and archive.calls == []


@pytest.mark.parametrize("value", [date(2026, 7, 15), datetime(2026, 7, 15, 9), "2026-07-15"])
def test_supported_dates_normalize(value):
    assert DailyResearchReportRunner._normalize_session_date(value) == "2026-07-15"


@pytest.mark.parametrize("value", ["bad", "../secret", "", "2026-07-15.json"])
def test_invalid_dates_fail_clearly(value):
    result = make_runner().run(session_date=value)
    assert result["status"] == "FAILED" and "ValueError:" in result["error"]


def test_none_resolves_india_local_date(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None): return datetime(2026, 7, 15, 1, tzinfo=tz)
    import services.daily_research_report_runner as module
    monkeypatch.setattr(module, "datetime", FixedDateTime)
    assert make_runner().run()["session_date"] == "2026-07-15"


def test_normalized_date_passed_and_preserved():
    journal, builder = Journal([entry()]), Builder()
    result = make_runner(journal=journal, builder=builder).run(session_date=date(2026, 7, 15))
    assert journal.calls == ["2026-07-15"] and builder.calls[0][2] == "2026-07-15" and result["session_date"] == "2026-07-15"


@pytest.mark.parametrize("entries, expected", [([], 0), ([entry()], 1), ([entry(value=1), entry(value=2)], 2), ([entry("2026-07-14"), entry()], 1)])
def test_journal_entries_load_filter_and_count(entries, expected):
    result = make_runner(journal=Journal(entries)).run(session_date="2026-07-15")
    assert result["journal_entries_loaded"] == expected


def test_journal_order_and_input_are_preserved():
    values = [entry(value=1), entry(value=2)]
    original = deepcopy(values)
    builder = Builder()
    make_runner(journal=Journal(values), builder=builder).run(session_date="2026-07-15")
    assert [item["value"] for item in builder.calls[0][0]] == [1, 2] and values == original


def test_journal_failure_is_failed_not_empty_and_stops_pipeline():
    repository, builder, archive = Repository(), Builder(), Archive()
    result = make_runner(journal=Journal(error=RuntimeError("journal unavailable")), repository=repository, builder=builder, archive=archive).run(session_date="2026-07-15")
    assert result["status"] == "FAILED" and result["journal_entries_loaded"] is None and "RuntimeError: journal unavailable" == result["error"]
    assert repository.calls == 0 and builder.calls == [] and archive.calls == []


@pytest.mark.parametrize("trades, expected", [([], 0), ([{"id": 1}], 1), ([{"id": 1}, {"id": 2}], 2)])
def test_trades_load_and_count(trades, expected):
    builder = Builder()
    result = make_runner(repository=Repository(trades), builder=builder).run(session_date="2026-07-15")
    assert result["paper_trades_loaded"] == expected and builder.calls[0][1] == trades


def test_trades_are_not_mutated_and_repository_is_read_only():
    trades = [{"nested": {"value": 1}}]
    original = deepcopy(trades)
    repository = Repository(trades)
    make_runner(repository=repository).run(session_date="2026-07-15")
    assert trades == original and not hasattr(repository, "save_trade") and not hasattr(repository, "delete_trade")


def test_repository_failure_is_failed_and_stops_build_and_archive():
    builder, archive = Builder(), Archive()
    result = make_runner(repository=Repository(error=ValueError("trade unavailable")), builder=builder, archive=archive).run(session_date="2026-07-15")
    assert result["status"] == "FAILED" and result["paper_trades_loaded"] is None and result["error"] == "ValueError: trade unavailable"
    assert builder.calls == [] and archive.calls == []


def test_report_build_receives_filtered_entries_trades_and_date():
    builder = Builder()
    make_runner(journal=Journal([entry(), entry("2026-07-14")]), repository=Repository([{"id": 1}]), builder=builder).run(session_date="2026-07-15")
    assert builder.calls == [([entry()], [{"id": 1}], "2026-07-15")]


@pytest.mark.parametrize("status, expected", [("COMPLETED", "COMPLETED"), ("COMPLETED_WITH_ERRORS", "COMPLETED_WITH_ERRORS")])
def test_report_status_is_preserved_and_archived(status, expected):
    archive = Archive()
    result = make_runner(builder=Builder(report("2026-07-15", status)), archive=archive).run(session_date="2026-07-15")
    assert result["status"] == expected and result["report_status"] == expected and len(archive.calls) == 1


def test_report_build_failure_is_failed_and_archive_not_called():
    archive = Archive()
    result = make_runner(builder=Builder(error=RuntimeError("report broken")), archive=archive).run(session_date="2026-07-15")
    assert result["status"] == "FAILED" and result["error"] == "RuntimeError: report broken" and archive.calls == []


def test_report_output_is_not_mutated_and_result_is_independent():
    output = report()
    runner = make_runner(builder=Builder(output))
    result = runner.run(session_date="2026-07-15")
    result["report"]["research_snapshot"]["final_decision"] = "CHANGED"
    assert output["research_snapshot"]["final_decision"] == "WAIT" and runner.run(session_date="2026-07-15")["report"]["research_snapshot"]["final_decision"] == "WAIT"


def test_archive_receives_exact_report_and_result_fields_are_preserved():
    output, archive = report(), Archive({"status": "SAVED", "success": True, "path": "/archive/2026-07-15.json"})
    result = make_runner(builder=Builder(output), archive=archive).run(session_date="2026-07-15")
    assert archive.calls == [output] and result["archive_status"] == "SAVED" and result["archive_success"] is True and result["archive_path"].endswith(".json")


def test_archive_failure_is_failed_with_error():
    result = make_runner(archive=Archive(error=OSError("disk full"))).run(session_date="2026-07-15")
    assert result["status"] == "FAILED" and result["error"] == "OSError: disk full"


def test_required_runner_keys_and_fresh_deterministic_results():
    runner = make_runner()
    first, second = runner.run(session_date="2026-07-15"), runner.run(session_date="2026-07-15")
    assert {"status", "read_only", "research_only", "session_date", "journal_entries_loaded", "paper_trades_loaded", "report_status", "archive_status", "archive_success", "archive_path", "report", "archive_result"} <= set(first)
    assert first["read_only"] is True and first["research_only"] is True and first == second and first is not second


def test_cli_prints_read_only_summary_unicode_and_correct_exit(monkeypatch, capsys):
    cli = importlib.import_module("daily_research_report_runner")
    class CliRunner:
        def run(self, **kwargs): return {"status": "COMPLETED", "session_date": "2026-07-15", "journal_entries_loaded": 1, "paper_trades_loaded": 2, "report_status": "COMPLETED", "archive_status": "SAVED", "archive_path": "/a.json", "report": report()}
    assert cli.main(["--date", "2026-07-15"], runner_factory=CliRunner) == 0
    text = capsys.readouterr().out
    assert "DAILY RESEARCH REPORT RUNNER" in text and "Mode: READ ONLY" in text and "₹" in text and "NO REAL ORDER WAS PLACED" in text
    assert "session_intelligence" not in text


@pytest.mark.parametrize("status, exit_code", [("COMPLETED_WITH_ERRORS", 0), ("FAILED", 1)])
def test_cli_exit_codes(status, exit_code):
    cli = importlib.import_module("daily_research_report_runner")
    class CliRunner:
        def run(self, **kwargs): return {"status": status, "report": {}}
    assert cli.main([], runner_factory=CliRunner) == exit_code


def test_runner_modules_have_no_execution_or_deletion_authority():
    source = (Path("services/daily_research_report_runner.py").read_text(encoding="utf-8") + Path("daily_research_report_runner.py").read_text(encoding="utf-8")).lower()
    forbidden = ("place_order", "placeorder", "broker", "open_paper", "close_paper", "delete_trade", "delete_report", "retrain", "strategy tuning", "risk_manager")
    assert not any(term in source for term in forbidden)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("status", "COMPLETED"),
        ("read_only", True),
        ("research_only", True),
        ("journal_entries_loaded", 1),
        ("paper_trades_loaded", 1),
        ("report_status", "COMPLETED"),
        ("archive_status", "SAVED"),
        ("archive_success", True),
        ("archive_path", "/archive/report.json"),
        ("session_date", "2026-07-15"),
    ],
)
def test_each_runner_result_field_is_correct(key, expected):
    result = make_runner(journal=Journal([entry()]), repository=Repository([{"id": 1}])).run(session_date="2026-07-15")
    assert result[key] == expected


@pytest.mark.parametrize(
    "fragment",
    [
        "Research Only: True",
        "Session Date: 2026-07-15",
        "Journal Entries Loaded: 1",
        "Paper Trades Loaded: 2",
        "Report Status: COMPLETED",
        "Archive Status: SAVED",
        "Archive Path: /a.json",
        "Research Observations:",
        "Research Snapshot:",
        "READ-ONLY MARKET RESEARCH",
    ],
)
def test_cli_contains_each_required_compact_output_line(monkeypatch, capsys, fragment):
    cli = importlib.import_module("daily_research_report_runner")
    class CliRunner:
        def run(self, **kwargs): return {"status": "COMPLETED", "session_date": "2026-07-15", "journal_entries_loaded": 1, "paper_trades_loaded": 2, "report_status": "COMPLETED", "archive_status": "SAVED", "archive_path": "/a.json", "report": report()}
    cli.main([], runner_factory=CliRunner)
    assert fragment in capsys.readouterr().out


@pytest.mark.parametrize("bad_entry", [None, "bad", {"session_date": "bad"}, {"value": 1}])
def test_non_matching_or_malformed_journal_entries_are_safely_excluded(bad_entry):
    result = make_runner(journal=Journal([entry(), bad_entry])).run(session_date="2026-07-15")
    assert result["status"] == "COMPLETED" and result["journal_entries_loaded"] == 1


def test_unsuccessful_archive_result_is_failed():
    result = make_runner(archive=Archive({"status": "ERROR", "success": False})).run(session_date="2026-07-15")
    assert result["status"] == "FAILED" and "RuntimeError:" in result["error"]


@pytest.mark.parametrize(
    "bad_report",
    [
        {},
        {"status": "COMPLETED", "read_only": False, "research_only": True, "session_date": "2026-07-15"},
        {"status": "COMPLETED", "read_only": True, "research_only": True, "session_date": "2026-07-14"},
    ],
)
def test_invalid_report_contract_fails_before_archiving(bad_report):
    archive = Archive()
    result = make_runner(builder=Builder(bad_report), archive=archive).run(session_date="2026-07-15")
    assert result["status"] == "FAILED" and archive.calls == []


@pytest.mark.parametrize("failure", [RuntimeError("journal"), ValueError("trades"), OSError("archive"), RuntimeError("report")])
def test_failure_error_text_always_includes_exception_type_and_message(failure):
    if isinstance(failure, RuntimeError) and str(failure) == "journal":
        runner = make_runner(journal=Journal(error=failure))
    elif isinstance(failure, ValueError):
        runner = make_runner(repository=Repository(error=failure))
    elif isinstance(failure, OSError):
        runner = make_runner(archive=Archive(error=failure))
    else:
        runner = make_runner(builder=Builder(error=failure))
    result = runner.run(session_date="2026-07-15")
    assert type(failure).__name__ + ": " + str(failure) == result["error"]

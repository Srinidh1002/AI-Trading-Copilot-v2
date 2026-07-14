"""Granular public-contract coverage for the research report archive."""

from copy import deepcopy
from datetime import date, datetime
import json
from pathlib import Path

import pytest

from services.research_report_archive import ResearchReportArchive


def report_for(session_date="2026-07-15", **changes):
    report = {
        "status": "COMPLETED",
        "read_only": True,
        "research_only": True,
        "session_date": session_date,
        "session_intelligence": {"nested": {"source": "session"}},
        "research_observations": ["Research observation ₹"],
        "research_snapshot": {"final_decision": "WAIT"},
    }
    report.update(changes)
    return report


def save_days(archive, *days):
    for day in days:
        archive.save_report(report_for(day))


def test_default_base_directory_is_research_reports():
    assert ResearchReportArchive().base_directory.name == "research_reports"


def test_custom_pathlib_directory_is_resolved(tmp_path):
    assert ResearchReportArchive(tmp_path / "archive").base_directory == (tmp_path / "archive").resolve()


def test_custom_path_like_directory_is_accepted(tmp_path):
    assert ResearchReportArchive(str(tmp_path / "archive")).base_directory == (tmp_path / "archive").resolve()


def test_constructor_does_not_create_directory_or_reports(tmp_path):
    directory = tmp_path / "archive"
    ResearchReportArchive(directory)
    assert not directory.exists()


def test_target_path_remains_under_configured_base(tmp_path):
    archive = ResearchReportArchive(tmp_path / "archive")
    _, target = archive._path_for_date("2026-07-15")
    assert target.parent == archive.base_directory


@pytest.mark.parametrize("value", [date(2026, 7, 15), datetime(2026, 7, 15, 12, 0), "2026-07-15"])
def test_supported_date_values_normalize(value):
    assert ResearchReportArchive._normalize_date(value) == "2026-07-15"


@pytest.mark.parametrize("value", ["2026-02-30", "", None, "../secret", "2026-07-15/../../secret", r"C:\temp\file", "2026-07-15.json"])
def test_invalid_or_unsafe_dates_are_rejected(value):
    with pytest.raises(ValueError):
        ResearchReportArchive._normalize_date(value)


@pytest.mark.parametrize(
    "candidate",
    [
        None,
        {"read_only": False, "research_only": True, "session_date": "2026-07-15"},
        {"read_only": True, "session_date": "2026-07-15"},
        {"read_only": True, "research_only": False, "session_date": "2026-07-15"},
        {"read_only": True, "research_only": True},
        {"read_only": True, "research_only": True, "session_date": "bad-date"},
    ],
)
def test_invalid_reports_are_rejected(tmp_path, candidate):
    with pytest.raises(ValueError):
        ResearchReportArchive(tmp_path).save_report(candidate)


def test_valid_research_report_is_accepted_without_mutation(tmp_path):
    report = report_for()
    original = deepcopy(report)
    ResearchReportArchive(tmp_path).save_report(report)
    assert report == original


def test_minimal_valid_research_report_is_accepted(tmp_path):
    minimal = {"read_only": True, "research_only": True, "session_date": "2026-07-15"}
    ResearchReportArchive(tmp_path).save_report(minimal)
    assert ResearchReportArchive(tmp_path).load_report("2026-07-15") == minimal


@pytest.mark.parametrize("session_date", [date(2026, 7, 15), datetime(2026, 7, 15, 12, 0)])
def test_save_accepts_date_and_datetime_session_dates(tmp_path, session_date):
    archive = ResearchReportArchive(tmp_path)
    archive.save_report(report_for(session_date))
    assert archive.load_report("2026-07-15")["session_date"].startswith("2026-07-15")


def test_save_creates_base_directory_and_correct_date_filename(tmp_path):
    archive = ResearchReportArchive(tmp_path / "archive")
    result = archive.save_report(report_for())
    assert (tmp_path / "archive" / "2026-07-15.json").is_file() and result["path"].endswith("2026-07-15.json")


def test_first_save_result_is_deterministic(tmp_path):
    result = ResearchReportArchive(tmp_path).save_report(report_for())
    assert result == {"status": "SAVED", "success": True, "session_date": "2026-07-15", "path": str((tmp_path / "2026-07-15.json").resolve()), "replaced_existing": False}


def test_second_save_replaces_existing_content_without_duplicate_file(tmp_path):
    archive = ResearchReportArchive(tmp_path)
    archive.save_report(report_for(research_snapshot={"version": 1}))
    result = archive.save_report(report_for(research_snapshot={"version": 2}))
    assert result["replaced_existing"] is True
    assert archive.load_report("2026-07-15")["research_snapshot"] == {"version": 2}
    assert len(list(tmp_path.glob("2026-07-15*.json"))) == 1


def test_saved_json_preserves_complete_unicode_nested_report(tmp_path):
    report = report_for(extra={"values": [1, {"rupee": "₹"}]})
    archive = ResearchReportArchive(tmp_path)
    archive.save_report(report)
    raw = (tmp_path / "2026-07-15.json").read_text(encoding="utf-8")
    assert "₹" in raw and json.loads(raw) == report


@pytest.mark.parametrize("field", ["session_intelligence", "research_snapshot", "research_observations"])
def test_important_report_sections_are_preserved(tmp_path, field):
    report = report_for()
    archive = ResearchReportArchive(tmp_path)
    archive.save_report(report)
    assert archive.load_report("2026-07-15")[field] == report[field]


def test_serialization_failure_preserves_existing_file_and_creates_no_partial_target(tmp_path):
    archive = ResearchReportArchive(tmp_path)
    archive.save_report(report_for(research_snapshot={"version": 1}))
    invalid = report_for(research_snapshot={"value": object()})
    with pytest.raises(TypeError):
        archive.save_report(invalid)
    assert archive.load_report("2026-07-15")["research_snapshot"] == {"version": 1}
    assert not list(tmp_path.glob("*.tmp"))


def test_write_failure_cleans_unique_temporary_file(tmp_path, monkeypatch):
    archive = ResearchReportArchive(tmp_path)
    import services.research_report_archive as module
    monkeypatch.setattr(module.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("replace failed")))
    with pytest.raises(OSError):
        archive.save_report(report_for())
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_replace_is_used(tmp_path, monkeypatch):
    archive = ResearchReportArchive(tmp_path)
    import services.research_report_archive as module
    calls = []
    original_replace = module.os.replace
    monkeypatch.setattr(module.os, "replace", lambda source, target: (calls.append((source, target)), original_replace(source, target))[1])
    archive.save_report(report_for())
    assert len(calls) == 1 and Path(calls[0][1]).name == "2026-07-15.json"


def test_existing_report_loads_as_complete_independent_object(tmp_path):
    archive = ResearchReportArchive(tmp_path)
    original = report_for(extra={"list": [1, 2]})
    archive.save_report(original)
    loaded = archive.load_report("2026-07-15")
    assert loaded == original and loaded is not original and loaded["extra"] is not original["extra"]


def test_missing_load_uses_not_found_contract(tmp_path):
    assert ResearchReportArchive(tmp_path).load_report("2026-07-15") == {"status": "NOT_FOUND", "success": False, "session_date": "2026-07-15", "report": None}


def test_two_loads_are_independent_and_mutation_does_not_change_file(tmp_path):
    archive = ResearchReportArchive(tmp_path)
    archive.save_report(report_for())
    first, second = archive.load_report("2026-07-15"), archive.load_report("2026-07-15")
    first["research_snapshot"]["final_decision"] = "CHANGED"
    assert second["research_snapshot"]["final_decision"] == "WAIT"
    assert archive.load_report("2026-07-15")["research_snapshot"]["final_decision"] == "WAIT"


@pytest.mark.parametrize("value", ["invalid", "../secret"])
def test_load_rejects_invalid_or_traversal_date(tmp_path, value):
    with pytest.raises(ValueError):
        ResearchReportArchive(tmp_path).load_report(value)


def test_list_empty_archive(tmp_path):
    assert ResearchReportArchive(tmp_path).list_reports() == {"status": "COMPLETED", "read_only": True, "count": 0, "reports": []}


def test_list_reports_is_chronological_and_has_deterministic_metadata(tmp_path):
    archive = ResearchReportArchive(tmp_path)
    save_days(archive, "2026-07-16", "2026-07-14", "2026-07-15")
    listed = archive.list_reports()
    assert [item["session_date"] for item in listed["reports"]] == ["2026-07-14", "2026-07-15", "2026-07-16"]
    assert listed["count"] == 3 and listed["reports"][0]["path"] == str((tmp_path / "2026-07-14.json").resolve())


@pytest.mark.parametrize("name", ["notes.txt", ".2026-07-15.random.tmp", "2026-99-99.json"])
def test_list_ignores_unrelated_temporary_and_malformed_files(tmp_path, name):
    archive = ResearchReportArchive(tmp_path)
    archive.save_report(report_for())
    (tmp_path / name).write_text("ignored", encoding="utf-8")
    assert archive.list_reports()["count"] == 1


def test_list_ignores_nested_directories(tmp_path):
    archive = ResearchReportArchive(tmp_path)
    archive.save_report(report_for())
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "2026-07-16.json").write_text("{}", encoding="utf-8")
    assert archive.list_reports()["count"] == 1


def test_range_load_empty_archive(tmp_path):
    assert ResearchReportArchive(tmp_path).load_reports()["count"] == 0


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (None, None, ["2026-07-14", "2026-07-15", "2026-07-16"]),
        ("2026-07-15", None, ["2026-07-15", "2026-07-16"]),
        (None, "2026-07-15", ["2026-07-14", "2026-07-15"]),
        ("2026-07-15", "2026-07-15", ["2026-07-15"]),
    ],
)
def test_range_load_filters_inclusively_and_chronologically(tmp_path, start, end, expected):
    archive = ResearchReportArchive(tmp_path)
    save_days(archive, "2026-07-14", "2026-07-15", "2026-07-16")
    result = archive.load_reports(start_date=start, end_date=end)
    assert [report["session_date"] for report in result["reports"]] == expected
    assert result["count"] == len(expected) and result["errors"] == []


def test_range_load_rejects_reversed_boundaries(tmp_path):
    with pytest.raises(ValueError, match="start_date"):
        ResearchReportArchive(tmp_path).load_reports(start_date="2026-07-16", end_date="2026-07-15")


def test_range_load_isolates_malformed_json_and_keeps_valid_reports(tmp_path):
    archive = ResearchReportArchive(tmp_path)
    save_days(archive, "2026-07-14", "2026-07-16")
    (tmp_path / "2026-07-15.json").write_text("{invalid", encoding="utf-8")
    result = archive.load_reports()
    assert [item["session_date"] for item in result["reports"]] == ["2026-07-14", "2026-07-16"]
    assert result["errors"][0]["session_date"] == "2026-07-15" and "ValueError:" in result["errors"][0]["error"]


def test_range_load_ignores_unrelated_and_temporary_files(tmp_path):
    archive = ResearchReportArchive(tmp_path)
    archive.save_report(report_for())
    (tmp_path / "noise.txt").write_text("x", encoding="utf-8")
    (tmp_path / ".save.tmp").write_text("x", encoding="utf-8")
    assert ResearchReportArchive(tmp_path).load_reports()["count"] == 1


def test_existing_report_is_deleted_and_another_remains(tmp_path):
    archive = ResearchReportArchive(tmp_path)
    save_days(archive, "2026-07-14", "2026-07-15")
    assert archive.delete_report("2026-07-14") == {"status": "DELETED", "success": True, "session_date": "2026-07-14"}
    assert not (tmp_path / "2026-07-14.json").exists() and (tmp_path / "2026-07-15.json").exists()


def test_missing_delete_is_deterministic(tmp_path):
    assert ResearchReportArchive(tmp_path).delete_report("2026-07-15") == {"status": "NOT_FOUND", "success": False, "session_date": "2026-07-15"}


def test_delete_leaves_nested_directories_and_unrelated_files_untouched(tmp_path):
    archive = ResearchReportArchive(tmp_path)
    archive.save_report(report_for())
    nested, unrelated = tmp_path / "nested", tmp_path / "notes.txt"
    nested.mkdir()
    unrelated.write_text("keep", encoding="utf-8")
    archive.delete_report("2026-07-15")
    assert nested.is_dir() and unrelated.read_text(encoding="utf-8") == "keep" and tmp_path.is_dir()


@pytest.mark.parametrize("value", ["bad", "../secret"])
def test_delete_rejects_invalid_or_traversal_date(tmp_path, value):
    with pytest.raises(ValueError):
        ResearchReportArchive(tmp_path).delete_report(value)


def test_production_module_has_no_execution_or_authority_terms():
    source = Path("services/research_report_archive.py").read_text(encoding="utf-8").lower()
    forbidden = ("place_order", "placeorder", "open_paper", "close_paper", "broker", "strategy tuning", "retrain", "risk_manager")
    assert not any(term in source for term in forbidden)


def test_archive_contract_is_persistence_and_research_only(tmp_path):
    archive = ResearchReportArchive(tmp_path)
    result = archive.save_report(report_for())
    assert result["success"] is True and archive.load_report("2026-07-15")["read_only"] is True

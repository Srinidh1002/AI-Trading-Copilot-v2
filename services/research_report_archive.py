"""Atomic, research-only persistence for completed daily research reports."""

from copy import deepcopy
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import tempfile


class ResearchReportArchive:
    """Store complete read-only DailyResearchReport outputs by session date."""

    _FILENAME_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")

    def __init__(self, base_directory=None):
        directory = (
            Path("data") / "research_reports"
            if base_directory is None
            else Path(base_directory)
        )
        self.base_directory = directory.expanduser().resolve()

    @staticmethod
    def _normalize_date(value):
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("session_date must use YYYY-MM-DD format.")
            try:
                return date.fromisoformat(normalized).isoformat()
            except ValueError as exc:
                raise ValueError("session_date must use YYYY-MM-DD format.") from exc
        raise ValueError("session_date must be a date, datetime, or YYYY-MM-DD string.")

    def _path_for_date(self, session_date):
        normalized = self._normalize_date(session_date)
        path = (self.base_directory / (normalized + ".json")).resolve()
        if path.parent != self.base_directory:
            raise ValueError("session_date must resolve to an archive file.")
        return normalized, path

    @staticmethod
    def _not_found(session_date):
        return {
            "status": "NOT_FOUND",
            "success": False,
            "session_date": session_date,
            "report": None,
        }

    def _validate_report(self, report):
        if not isinstance(report, dict):
            raise ValueError("report must be a dictionary.")
        if report.get("read_only") is not True:
            raise ValueError("report['read_only'] must be True.")
        if report.get("research_only") is not True:
            raise ValueError("report['research_only'] must be True.")
        session_date, _ = self._path_for_date(report.get("session_date"))
        return session_date

    @staticmethod
    def _json_default(value):
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        raise TypeError("Object of type {} is not JSON serializable".format(type(value).__name__))

    def save_report(self, report):
        """Atomically save one complete daily research report."""
        session_date = self._validate_report(report)
        _, target_path = self._path_for_date(session_date)
        serialized = json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=self._json_default,
        )
        replaced_existing = target_path.is_file()
        self.base_directory.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.base_directory,
                prefix="." + session_date + ".",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                file.write(serialized)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, target_path)
        except Exception:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise
        return {
            "status": "SAVED",
            "success": True,
            "session_date": session_date,
            "path": str(target_path),
            "replaced_existing": replaced_existing,
        }

    def load_report(self, session_date):
        """Load an independent copy of the exact archived daily report."""
        normalized, path = self._path_for_date(session_date)
        if not path.is_file():
            return self._not_found(normalized)
        try:
            with path.open("r", encoding="utf-8") as file:
                report = json.load(file)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON in research report archive: {}".format(exc)) from exc
        if not isinstance(report, dict):
            raise ValueError("Archived research report must be a dictionary.")
        return deepcopy(report)

    def list_reports(self):
        """List valid daily archive filenames in chronological order."""
        reports = []
        if self.base_directory.is_dir():
            for path in self.base_directory.iterdir():
                if not path.is_file():
                    continue
                match = self._FILENAME_PATTERN.match(path.name)
                if match is None:
                    continue
                try:
                    session_date = self._normalize_date(match.group(1))
                except ValueError:
                    continue
                reports.append({"session_date": session_date, "path": str(path.resolve())})
        reports.sort(key=lambda item: item["session_date"])
        return {"status": "COMPLETED", "read_only": True, "count": len(reports), "reports": reports}

    def load_reports(self, *, start_date=None, end_date=None):
        """Load complete daily reports in an inclusive chronological date range."""
        start = self._normalize_date(start_date) if start_date is not None else None
        end = self._normalize_date(end_date) if end_date is not None else None
        if start is not None and end is not None and start > end:
            raise ValueError("start_date must not be after end_date.")
        reports, errors = [], []
        for metadata in self.list_reports()["reports"]:
            session_date = metadata["session_date"]
            if (start is not None and session_date < start) or (end is not None and session_date > end):
                continue
            try:
                loaded = self.load_report(session_date)
                if loaded.get("status") != "NOT_FOUND":
                    reports.append(loaded)
            except Exception as exc:
                errors.append({"session_date": session_date, "error": "{}: {}".format(type(exc).__name__, str(exc))})
        return {"status": "COMPLETED", "read_only": True, "start_date": start, "end_date": end, "count": len(reports), "reports": reports, "errors": errors}

    def delete_report(self, session_date):
        """Delete only the exact daily archive JSON file for the supplied date."""
        normalized, path = self._path_for_date(session_date)
        if not path.is_file():
            return {"status": "NOT_FOUND", "success": False, "session_date": normalized}
        path.unlink()
        return {"status": "DELETED", "success": True, "session_date": normalized}

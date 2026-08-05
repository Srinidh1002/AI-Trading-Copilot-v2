"""Atomic archive for immutable PAPER certification reports."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from services.contracts.paper_certification_reporting_v1 import (
    PaperCertificationDailyReportV1,
    PaperCertificationMonthlyReportV1,
    PaperCertificationWeeklyReportV1,
)


_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_TYPES = {
    PaperCertificationDailyReportV1: "daily",
    PaperCertificationWeeklyReportV1: "weekly",
    PaperCertificationMonthlyReportV1: "monthly",
}


class PaperCertificationReportArchive:
    """Write-once archive with duplicate and conflict detection."""

    def __init__(
        self,
        root_directory: str | Path = (
            "data/paper_trading/certified_runtime/"
            "certification_reports"
        ),
    ) -> None:
        self.root_directory = Path(root_directory)

    @staticmethod
    def _safe_report_id(report_id: str) -> str:
        if type(report_id) is not str:
            raise TypeError("report_id")
        cleaned = report_id.strip()
        if not _SAFE.fullmatch(cleaned):
            raise ValueError("unsafe report_id")
        return cleaned

    def _path(self, report) -> Path:
        report_type = _TYPES.get(type(report))
        if report_type is None:
            raise TypeError("unsupported certification report")
        report_id = self._safe_report_id(report.report_id)
        if report_type == "daily":
            period = report.session_date.isoformat()
        elif report_type == "weekly":
            period = (
                f"{report.week_started_on.isoformat()}_"
                f"{report.week_ended_on.isoformat()}"
            )
        else:
            period = report.month_started_on.strftime("%Y-%m")
        return (
            self.root_directory
            / report_type
            / period
            / f"{report_id}.json"
        )

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            text=True,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(content)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            try:
                directory_descriptor = os.open(
                    path.parent,
                    os.O_RDONLY,
                )
            except OSError:
                directory_descriptor = None
            if directory_descriptor is not None:
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, report) -> dict[str, object]:
        path = self._path(report)
        content = report.to_json()
        if path.exists():
            existing = path.read_text(
                encoding="utf-8"
            ).strip()
            if existing == content:
                return {
                    "status": "DUPLICATE_SAME_PAYLOAD",
                    "saved": False,
                    "path": str(path.resolve()),
                    "report_id": report.report_id,
                    "semantic_hash": report.semantic_hash,
                }
            raise ValueError(
                "conflicting immutable certification report"
            )
        self._atomic_write(path, content)
        return {
            "status": "SAVED",
            "saved": True,
            "path": str(path.resolve()),
            "report_id": report.report_id,
            "semantic_hash": report.semantic_hash,
        }

    def load_raw(self, report) -> dict[str, object]:
        path = self._path(report)
        if not path.is_file():
            raise FileNotFoundError(path)
        value = json.loads(path.read_text(encoding="utf-8"))
        if type(value) is not dict:
            raise ValueError("invalid archived report")
        return value

"""Immutable index of archived Task 9 daily certification reports."""
from __future__ import annotations

import json
import os
from pathlib import Path


def _run_id(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("official_run_id")
    return value.strip()


class Task9DailyReportIndex:
    """Append-only daily-report index bound to one Task 9 official run."""

    SCHEMA_VERSION = 2

    def __init__(
        self,
        *,
        official_run_id: str,
        file_path: str | Path = (
            "data/paper_trading/certified_runtime/"
            "task9_daily_report_index.json"
        ),
    ) -> None:
        self.official_run_id = _run_id(
            official_run_id
        )
        self.file_path = Path(file_path)

        # Existing persistence must prove that it belongs to
        # this exact official Task 9 certification run.
        if self.file_path.exists():
            self._read_document()

    def _empty_document(self) -> dict[str, object]:
        return {
            "version": self.SCHEMA_VERSION,
            "official_run_id": self.official_run_id,
            "records": {},
        }

    def _validate_document(
        self,
        document: object,
    ) -> dict[str, object]:
        if type(document) is not dict:
            raise ValueError(
                "Task 9 daily report index must be a JSON object"
            )

        if set(document) != {
            "version",
            "official_run_id",
            "records",
        }:
            raise ValueError(
                "Task 9 daily report index fields"
            )

        if document.get("version") != self.SCHEMA_VERSION:
            raise ValueError(
                "unsupported Task 9 daily report index version"
            )

        persisted_run_id = _run_id(
            document.get("official_run_id")
        )

        if persisted_run_id != self.official_run_id:
            raise ValueError(
                "TASK9_OFFICIAL_RUN_ID_MISMATCH"
            )

        records = document.get("records")
        if type(records) is not dict:
            raise ValueError(
                "Task 9 daily report index records"
            )

        normalized: dict[
            str,
            dict[str, str],
        ] = {}

        for session_date, raw in records.items():
            if (
                type(session_date) is not str
                or not session_date.strip()
            ):
                raise ValueError("session_date")

            if type(raw) is not dict:
                raise ValueError(
                    "Task 9 index record"
                )

            required = {
                "report_id",
                "session_date",
                "semantic_hash",
                "archive_path",
            }

            if set(raw) != required:
                raise ValueError(
                    "Task 9 index record fields"
                )

            if raw.get("session_date") != session_date:
                raise ValueError(
                    "Task 9 index session-date mismatch"
                )

            report_id = raw.get("report_id")
            semantic_hash = raw.get(
                "semantic_hash"
            )
            archive_path = raw.get(
                "archive_path"
            )

            if (
                type(report_id) is not str
                or not report_id.strip()
            ):
                raise ValueError("report_id")

            if (
                type(semantic_hash) is not str
                or len(semantic_hash) != 64
            ):
                raise ValueError(
                    "semantic_hash"
                )

            if (
                type(archive_path) is not str
                or not archive_path.strip()
            ):
                raise ValueError(
                    "archive_path"
                )

            path = Path(archive_path)

            if (
                path.is_absolute()
                or ".." in path.parts
            ):
                raise ValueError(
                    "archive_path must be safe relative path"
                )

            normalized[session_date] = {
                "report_id": report_id.strip(),
                "session_date": session_date,
                "semantic_hash": semantic_hash,
                "archive_path": path.as_posix(),
            }

        return {
            "version": self.SCHEMA_VERSION,
            "official_run_id": persisted_run_id,
            "records": normalized,
        }

    def _read_document(
        self,
    ) -> dict[str, object]:
        if not self.file_path.exists():
            return self._empty_document()

        try:
            value = json.loads(
                self.file_path.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "invalid JSON in Task 9 daily report index"
            ) from exc

        return self._validate_document(
            value
        )

    def _write_document(
        self,
        document: dict[str, object],
    ) -> None:
        validated = self._validate_document(
            document
        )

        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = self.file_path.with_name(
            self.file_path.name + ".tmp"
        )

        try:
            with temporary.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                json.dump(
                    validated,
                    handle,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temporary,
                self.file_path,
            )

        finally:
            temporary.unlink(
                missing_ok=True
            )

    def save(
        self,
        *,
        report_id: str,
        session_date: str,
        semantic_hash: str,
        archive_path: str,
    ) -> str:
        if (
            type(report_id) is not str
            or not report_id.strip()
        ):
            raise ValueError(
                "report_id"
            )

        if (
            type(session_date) is not str
            or not session_date.strip()
        ):
            raise ValueError(
                "session_date"
            )

        if (
            type(semantic_hash) is not str
            or len(semantic_hash) != 64
        ):
            raise ValueError(
                "semantic_hash"
            )

        path = Path(
            archive_path
        )

        if (
            path.is_absolute()
            or ".." in path.parts
        ):
            raise ValueError(
                "archive_path must be safe relative path"
            )

        session = session_date.strip()

        record = {
            "report_id": report_id.strip(),
            "session_date": session,
            "semantic_hash": semantic_hash,
            "archive_path": path.as_posix(),
        }

        document = self._read_document()
        records = document["records"]

        existing = records.get(
            session
        )

        if existing is not None:
            if existing == record:
                return (
                    "DUPLICATE_SAME_PAYLOAD"
                )

            raise ValueError(
                "TASK9_DAILY_REPORT_INDEX_CONFLICT"
            )

        if any(
            item["report_id"]
            == report_id.strip()
            for item in records.values()
        ):
            raise ValueError(
                "TASK9_REPORT_ID_ALREADY_INDEXED"
            )

        records[session] = record

        self._write_document(
            document
        )

        return "SAVED"

    def all_records(
        self,
    ) -> tuple[dict[str, str], ...]:
        records = self._read_document()[
            "records"
        ]

        return tuple(
            dict(records[key])
            for key in sorted(records)
        )

    def count(self) -> int:
        return len(
            self._read_document()[
                "records"
            ]
        )

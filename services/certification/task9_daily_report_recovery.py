"""Restart recovery of immutable Task 9 daily certification evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from services.certification.task9_daily_report_index import (
    Task9DailyReportIndex,
)


def _canonical_json(
    value: object,
) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _semantic_hash(
    value: object,
) -> str:
    return hashlib.sha256(
        _canonical_json(
            value
        ).encode("utf-8")
    ).hexdigest()


def _run_id(
    value: object,
) -> str:
    if (
        type(value) is not str
        or not value.strip()
    ):
        raise ValueError(
            "official_run_id"
        )

    return value.strip()


def recover_task9_daily_reports(
    *,
    index: Task9DailyReportIndex,
    official_run_id: str,
    archive_root: str | Path = (
        "data/paper_trading/certified_runtime/"
        "certification_reports"
    ),
) -> tuple[dict[str, object], ...]:
    """Recover verified reports for one exact official Task 9 run."""

    if type(index) is not Task9DailyReportIndex:
        raise TypeError(
            "index"
        )

    run_id = _run_id(
        official_run_id
    )

    if (
        index.official_run_id
        != run_id
    ):
        raise ValueError(
            "TASK9_OFFICIAL_RUN_ID_MISMATCH"
        )

    root = Path(
        archive_root
    ).resolve()

    recovered: list[
        dict[str, object]
    ] = []

    prediction_ids: set[str] = set()
    session_dates: set[str] = set()

    for record in index.all_records():
        session_date = record[
            "session_date"
        ]

        if session_date in session_dates:
            raise ValueError(
                "duplicate Task 9 recovered session"
            )

        session_dates.add(
            session_date
        )

        relative = Path(
            record["archive_path"]
        )

        if (
            relative.is_absolute()
            or ".." in relative.parts
        ):
            raise ValueError(
                "unsafe Task 9 archive path"
            )

        path = (
            root / relative
        ).resolve()

        try:
            path.relative_to(
                root
            )
        except ValueError as exc:
            raise ValueError(
                "Task 9 archive path escapes root"
            ) from exc

        if not path.is_file():
            raise FileNotFoundError(
                path
            )

        try:
            raw = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "invalid archived Task 9 daily report JSON"
            ) from exc

        if type(raw) is not dict:
            raise ValueError(
                "archived Task 9 report must be object"
            )

        if (
            raw.get("schema_version")
            != "paper_certification_daily_report.v1"
        ):
            raise ValueError(
                "Task 9 archived report schema"
            )

        if (
            raw.get("report_id")
            != record["report_id"]
        ):
            raise ValueError(
                "Task 9 report-id mismatch"
            )

        if (
            raw.get("session_date")
            != session_date
        ):
            raise ValueError(
                "Task 9 session-date mismatch"
            )

        if (
            raw.get("report_status")
            != "RECONCILED"
        ):
            raise ValueError(
                "Task 9 report must be reconciled"
            )

        if (
            raw.get("execution_mode")
            != "PAPER"
            or raw.get(
                "live_execution_eligible"
            )
            is not False
            or raw.get(
                "broker_order_submission"
            )
            is not False
            or raw.get(
                "read_only"
            )
            is not True
        ):
            raise ValueError(
                "Task 9 recovered report safety"
            )

        actual_hash = _semantic_hash(
            raw
        )

        if (
            actual_hash
            != record["semantic_hash"]
        ):
            raise ValueError(
                "Task 9 archived report semantic-hash mismatch"
            )

        facts = raw.get(
            "prediction_facts"
        )

        if type(facts) is not list:
            raise ValueError(
                "Task 9 prediction_facts"
            )

        for fact in facts:
            if type(fact) is not dict:
                raise ValueError(
                    "Task 9 prediction fact"
                )

            prediction_id = fact.get(
                "prediction_id"
            )

            if (
                type(prediction_id)
                is not str
                or not prediction_id.strip()
            ):
                raise ValueError(
                    "Task 9 prediction_id"
                )

            if (
                prediction_id
                in prediction_ids
            ):
                raise ValueError(
                    "duplicate prediction across Task 9 reports"
                )

            prediction_ids.add(
                prediction_id
            )

        recovered.append(
            raw
        )

    return tuple(
        recovered
    )

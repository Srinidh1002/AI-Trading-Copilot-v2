"""Run-scoped Task 9 daily-report-index authority and campaign aggregation."""

from __future__ import annotations

import json
from pathlib import Path

from services.certification.task9_daily_report_index import (
    Task9DailyReportIndex,
)
from services.certification.task9_daily_report_recovery import (
    recover_task9_daily_reports,
)


_LEGACY_INDEX_NAME = "daily-report-index.json"
_RUN_INDEX_DIRECTORY = "daily-report-indexes"


def _official_run_id(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("official_run_id")

    run_id = value.strip()

    if (
        run_id in {".", ".."}
        or "/" in run_id
        or "\\" in run_id
    ):
        raise ValueError("unsafe official_run_id")

    return run_id


def task9_daily_report_index_path(
    root: str | Path,
    official_run_id: str,
) -> Path:
    """Return the canonical run-scoped daily-report-index path."""

    run_id = _official_run_id(
        official_run_id
    )

    return (
        Path(root)
        / _RUN_INDEX_DIRECTORY
        / f"{run_id}.json"
    )


def _persisted_index_run_id(
    path: Path,
) -> str | None:
    if not path.exists():
        return None

    try:
        raw = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            "invalid Task 9 daily report index"
        ) from exc

    if type(raw) is not dict:
        raise ValueError(
            "invalid Task 9 daily report index"
        )

    return _official_run_id(
        raw.get("official_run_id")
    )


def open_task9_daily_report_index_for_run(
    *,
    root: str | Path,
    official_run_id: str,
) -> Task9DailyReportIndex:
    """Open one exact run index with legacy compatibility.

    New writes always use the run-scoped layout.  The legacy root-level
    index is read only when it proves ownership by the requested run.
    """

    root_path = Path(root)
    run_id = _official_run_id(
        official_run_id
    )

    scoped_path = (
        task9_daily_report_index_path(
            root_path,
            run_id,
        )
    )

    if scoped_path.exists():
        return Task9DailyReportIndex(
            official_run_id=run_id,
            file_path=scoped_path,
        )

    legacy_path = (
        root_path
        / _LEGACY_INDEX_NAME
    )

    legacy_run_id = (
        _persisted_index_run_id(
            legacy_path
        )
    )

    if legacy_run_id == run_id:
        return Task9DailyReportIndex(
            official_run_id=run_id,
            file_path=legacy_path,
        )

    # Return the canonical empty/new run-scoped authority.  Callers that
    # require finalized prior evidence will then fail closed on missing
    # records rather than adopting another run's index.
    return Task9DailyReportIndex(
        official_run_id=run_id,
        file_path=scoped_path,
    )


def _campaign_run_ids(
    *,
    root: Path,
    current_official_run_id: str,
) -> tuple[str, ...]:
    """Resolve all official runs belonging to the current run's campaign."""

    current = _official_run_id(
        current_official_run_id
    )

    manifest_root = (
        root
        / "official-run-manifests"
    )

    if not manifest_root.exists():
        return (current,)

    manifests: list[
        tuple[str, str]
    ] = []

    for path in sorted(
        manifest_root.glob("*.json")
    ):
        try:
            raw = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "invalid Task 9 official run manifest"
            ) from exc

        if type(raw) is not dict:
            raise ValueError(
                "invalid Task 9 official run manifest"
            )

        run_id = raw.get(
            "official_run_id"
        )
        campaign_id = raw.get(
            "campaign_id"
        )

        if (
            type(run_id) is not str
            or not run_id.strip()
            or type(campaign_id) is not str
            or not campaign_id.strip()
        ):
            raise ValueError(
                "invalid Task 9 official run manifest identity"
            )

        manifests.append(
            (
                run_id.strip(),
                campaign_id.strip(),
            )
        )

    current_campaign = next(
        (
            campaign_id
            for run_id, campaign_id
            in manifests
            if run_id == current
        ),
        None,
    )

    if current_campaign is None:
        return (current,)

    return tuple(
        sorted(
            {
                run_id
                for run_id, campaign_id
                in manifests
                if campaign_id
                == current_campaign
            }
            | {current}
        )
    )


def recover_task9_campaign_daily_reports(
    *,
    root: str | Path,
    current_official_run_id: str,
    archive_root: str | Path,
) -> tuple[dict[str, object], ...]:
    """Recover verified archived reports across this campaign's run indexes."""

    root_path = Path(root)

    allowed_run_ids = set(
        _campaign_run_ids(
            root=root_path,
            current_official_run_id=(
                current_official_run_id
            ),
        )
    )

    candidate_paths: list[Path] = []

    legacy_path = (
        root_path
        / _LEGACY_INDEX_NAME
    )

    if legacy_path.exists():
        candidate_paths.append(
            legacy_path
        )

    scoped_root = (
        root_path
        / _RUN_INDEX_DIRECTORY
    )

    if scoped_root.exists():
        candidate_paths.extend(
            sorted(
                scoped_root.glob("*.json")
            )
        )

    reports_by_session: dict[
        str,
        dict[str, object],
    ] = {}

    seen_index_paths: set[Path] = set()

    for path in candidate_paths:
        resolved = path.resolve()

        if resolved in seen_index_paths:
            continue

        seen_index_paths.add(
            resolved
        )

        run_id = (
            _persisted_index_run_id(
                path
            )
        )

        if run_id not in allowed_run_ids:
            continue

        assert run_id is not None

        index = Task9DailyReportIndex(
            official_run_id=run_id,
            file_path=path,
        )

        recovered = (
            recover_task9_daily_reports(
                index=index,
                official_run_id=run_id,
                archive_root=archive_root,
            )
        )

        for report in recovered:
            if type(report) is not dict:
                raise ValueError(
                    "invalid recovered Task 9 daily report"
                )

            session_date = report.get(
                "session_date"
            )

            if (
                type(session_date) is not str
                or not session_date.strip()
            ):
                raise ValueError(
                    "invalid recovered Task 9 session date"
                )

            existing = (
                reports_by_session.get(
                    session_date
                )
            )

            if (
                existing is not None
                and existing != report
            ):
                raise ValueError(
                    "TASK9_CROSS_RUN_DAILY_REPORT_CONFLICT"
                )

            reports_by_session[
                session_date
            ] = report

    return tuple(
        reports_by_session[key]
        for key in sorted(
            reports_by_session
        )
    )


__all__ = (
    "open_task9_daily_report_index_for_run",
    "recover_task9_campaign_daily_reports",
    "task9_daily_report_index_path",
)

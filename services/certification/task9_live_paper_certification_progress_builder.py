"""Build Task 9 100+100 progress from immutable certification evidence."""
from __future__ import annotations

from services.contracts.paper_certification_reporting_v1 import (
    PaperCertificationDailyReportV1,
)
from services.contracts.task9_live_paper_certification_progress_v1 import (
    Task9LivePaperCertificationProgressV1,
    Task9MarketProgressV1,
)


def _field(item, name: str):
    if type(item) is dict:
        if name not in item:
            raise ValueError(f"missing {name}")
        return item[name]
    return getattr(item, name)


def _facts(report):
    return _field(report, "prediction_facts")


def _sequence(report, name: str):
    value = _field(report, name)
    if type(value) not in (tuple, list):
        raise ValueError(name)
    return value


def _validate_raw_report(report: dict[str, object]) -> None:
    if (
        report.get("schema_version")
        != "paper_certification_daily_report.v1"
    ):
        raise ValueError("Task 9 daily report schema")

    if report.get("report_status") != "RECONCILED":
        raise ValueError(
            "Task 9 daily report must be reconciled"
        )

    if (
        report.get("execution_mode") != "PAPER"
        or report.get("live_execution_eligible") is not False
        or report.get("broker_order_submission") is not False
        or report.get("read_only") is not True
    ):
        raise ValueError(
            "Task 9 daily report safety"
        )

    for name in (
        "prediction_facts",
        "excluded_audit",
        "unresolved_audit",
        "incidents",
        "duplicate_attempts",
    ):
        if type(report.get(name)) is not list:
            raise ValueError(name)


def _market_progress(
    market: str,
    facts,
) -> Task9MarketProgressV1:
    market_facts = tuple(
        item
        for item in facts
        if _field(item, "market") == market
    )

    completed_trades = sum(
        bool(
            _field(item, "officially_counted")
            and _field(item, "action") in {"CALL", "PUT"}
            and _field(item, "entry_occurred")
            and _field(item, "closed_position")
            and _field(item, "lifecycle_status") == "RESOLVED"
            and _field(item, "reconciliation_status")
            == "RECONCILED"
        )
        for item in market_facts
    )

    pending_entered = sum(
        bool(
            _field(item, "action") in {"CALL", "PUT"}
            and _field(item, "entry_occurred")
            and not _field(item, "closed_position")
        )
        for item in market_facts
    )

    completed_no_trade = tuple(
        item
        for item in market_facts
        if (
            _field(item, "action") == "NO_TRADE"
            and _field(item, "counting_status") == "INCLUDED_NON_TRADE"
            and _field(item, "lifecycle_status") == "RESOLVED"
            and _field(item, "outcome")
            in {
                "NO_TRADE_CORRECT",
                "NO_TRADE_MISSED_MOVE",
            }
        )
    )

    return Task9MarketProgressV1(
        market=market,
        target_trade_count=100,
        completed_live_paper_trades=completed_trades,
        pending_entered_trades=pending_entered,
        no_trade_completed=len(completed_no_trade),
        no_trade_passed=sum(
            _field(item, "outcome")
            == "NO_TRADE_CORRECT"
            for item in completed_no_trade
        ),
        no_trade_failed=sum(
            _field(item, "outcome")
            == "NO_TRADE_MISSED_MOVE"
            for item in completed_no_trade
        ),
    )


def _build_progress(
    reports,
) -> Task9LivePaperCertificationProgressV1:
    session_dates = tuple(
        str(_field(item, "session_date"))
        for item in reports
    )

    if len(set(session_dates)) != len(session_dates):
        raise ValueError(
            "duplicate Task 9 daily certification session"
        )

    facts = tuple(
        fact
        for report in reports
        for fact in _sequence(report, "prediction_facts")
    )

    prediction_ids = tuple(
        _field(item, "prediction_id")
        for item in facts
    )

    if len(set(prediction_ids)) != len(prediction_ids):
        raise ValueError(
            "duplicate prediction across Task 9 reports"
        )

    excluded = tuple(
        item
        for report in reports
        for item in _sequence(report, "excluded_audit")
    )

    unresolved_items = tuple(
        item
        for report in reports
        for item in _sequence(report, "unresolved_audit")
    )

    duplicates = tuple(
        item
        for report in reports
        for item in _sequence(report, "duplicate_attempts")
    )

    incidents = tuple(
        item
        for report in reports
        for item in _sequence(report, "incidents")
    )

    nifty = _market_progress("NIFTY", facts)
    sensex = _market_progress("SENSEX", facts)

    replay_excluded = sum(
        _field(item, "status") == "EXCLUDED_REPLAY"
        for item in excluded
    )

    invalid_excluded = sum(
        (
            _field(item, "status")
            in {
                "EXCLUDED_INVALID_EVIDENCE",
                "EXCLUDED_CHILD_FAILURE",
                "EXCLUDED_DATA_INCIDENT",
                "EXCLUDED_DATA_UNAVAILABLE",
            }
            or str(_field(item, "status")).startswith(
                "EXCLUDED_RECONCILIATION_"
            )
        )
        for item in excluded
    )

    # Incidents remain visible independently from the /100 counters.
    # A resolved INFO/WARNING event is operational evidence, not an
    # automatic invalid exclusion. Unresolved incidents and ERROR/CRITICAL
    # incidents are fail-closed in exclusion analytics.
    invalid_excluded += sum(
        (
            _field(item, "resolved") is not True
            or _field(item, "severity")
            in {"ERROR", "CRITICAL"}
        )
        for item in incidents
    )

    return Task9LivePaperCertificationProgressV1(
        nifty=nifty,
        sensex=sensex,
        replay_excluded=replay_excluded,
        duplicate_excluded=len(duplicates),
        invalid_excluded=invalid_excluded,
        unresolved=len(unresolved_items),
        certification_complete=(
            nifty.target_reached
            and sensex.target_reached
        ),
    )


def build_task9_live_paper_certification_progress(
    reports: tuple[PaperCertificationDailyReportV1, ...],
) -> Task9LivePaperCertificationProgressV1:
    """Build progress from exact typed daily reports."""

    if type(reports) is not tuple:
        raise TypeError("reports")

    if any(
        type(item) is not PaperCertificationDailyReportV1
        for item in reports
    ):
        raise TypeError("reports")

    return _build_progress(reports)


def build_task9_live_paper_certification_progress_from_raw(
    reports: tuple[dict[str, object], ...],
) -> Task9LivePaperCertificationProgressV1:
    """Build restart progress from verified archived raw reports."""

    if type(reports) is not tuple:
        raise TypeError("reports")

    if any(type(item) is not dict for item in reports):
        raise TypeError("reports")

    for report in reports:
        _validate_raw_report(report)

    return _build_progress(reports)

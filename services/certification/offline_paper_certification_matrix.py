"""Deterministic Task 7 offline PAPER certification matrix."""
from __future__ import annotations

from datetime import datetime

from services.contracts.offline_paper_certification_v1 import (
    OfflinePaperCertificationCheckV1,
    OfflinePaperCertificationReportV1,
)


_REQUIRED_CHECKS = (
    (
        "two-market-selection",
        "TWO_MARKET",
        "NIFTY and SENSEX deterministic ranking",
        (
            "Exactly NIFTY/NSE and SENSEX/BSE are evaluated.",
            "One market wins or the result fails closed to no trade.",
            "Losing-market reasons remain visible.",
        ),
    ),
    (
        "capital-risk-authority",
        "CAPITAL_RISK",
        "Capital and maximum-loss authority",
        (
            "Capital required cannot exceed usable capital.",
            "Maximum loss remains bounded by supplied capital.",
            "Duplicate entry reservation is prevented.",
        ),
    ),
    (
        "paper-lifecycle",
        "PAPER_LIFECYCLE",
        "Complete PAPER trade lifecycle",
        (
            "Entry, HOLD, partial targets, protected stop, and closure are deterministic.",
            "Capital release and journal persistence occur only after closure.",
            "No broker order is submitted.",
        ),
    ),
    (
        "restart-recovery",
        "RESTART_RECOVERY",
        "Restart and replay recovery",
        (
            "Active positions recover from persistent storage.",
            "Processed event identifiers make transitions idempotent.",
            "Closed positions do not recover as active.",
        ),
    ),
    (
        "operator-dashboard",
        "OPERATOR_DASHBOARD",
        "Read-only operator dashboard",
        (
            "Certified runtime state projects into one immutable view model.",
            "NIFTY, SENSEX, recommendation, capital, trade, and health are visible.",
            "Dashboard contains no trade or broker action controls.",
        ),
    ),
    (
        "safety-isolation",
        "SAFETY_ISOLATION",
        "Offline PAPER and broker isolation",
        (
            "Certification requires no network access.",
            "Execution mode remains PAPER.",
            "Live eligibility and broker submission remain disabled.",
        ),
    ),
)


def build_offline_paper_certification_report(
    *,
    report_id: str,
    generated_at: datetime,
    branch_name: str,
    commit_sha: str,
    failed_check_ids: tuple[str, ...] = (),
    blocked_check_ids: tuple[str, ...] = (),
    additional_warnings: tuple[str, ...] = (),
) -> OfflinePaperCertificationReportV1:
    """Build one deterministic certification report from explicit outcomes."""

    if not isinstance(failed_check_ids, tuple):
        raise TypeError("failed_check_ids")
    if not isinstance(blocked_check_ids, tuple):
        raise TypeError("blocked_check_ids")
    if not isinstance(additional_warnings, tuple):
        raise TypeError("additional_warnings")

    known_ids = {item[0] for item in _REQUIRED_CHECKS}
    failed = set(failed_check_ids)
    blocked = set(blocked_check_ids)

    unknown = (failed | blocked) - known_ids
    if unknown:
        raise ValueError("unknown certification check")
    if failed & blocked:
        raise ValueError("check cannot be both failed and blocked")

    checks = []
    for check_id, category, name, evidence in _REQUIRED_CHECKS:
        if check_id in failed:
            status = "FAILED"
            blockers = ("CERTIFICATION_ASSERTION_FAILED",)
        elif check_id in blocked:
            status = "BLOCKED"
            blockers = ("CERTIFICATION_DEPENDENCY_BLOCKED",)
        else:
            status = "PASSED"
            blockers = ()

        checks.append(
            OfflinePaperCertificationCheckV1(
                check_id=check_id,
                category=category,
                name=name,
                status=status,
                evidence=evidence,
                blockers=blockers,
                warnings=additional_warnings,
            )
        )

    checks_tuple = tuple(checks)
    passed_count = sum(
        check.status == "PASSED" for check in checks_tuple
    )
    failed_count = sum(
        check.status == "FAILED" for check in checks_tuple
    )
    blocked_count = sum(
        check.status == "BLOCKED" for check in checks_tuple
    )

    if failed_count:
        overall = "FAILED"
    elif blocked_count:
        overall = "BLOCKED"
    else:
        overall = "PASSED"

    return OfflinePaperCertificationReportV1(
        report_id=report_id,
        generated_at=generated_at,
        branch_name=branch_name,
        commit_sha=commit_sha,
        checks=checks_tuple,
        overall_status=overall,
        passed_count=passed_count,
        failed_count=failed_count,
        blocked_count=blocked_count,
    )

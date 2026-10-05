"""Fail-closed pre-LIVE eligibility authority for the index rollout.

This is a readiness/reporting contract only. It deliberately exposes no order,
modify, cancel or broker-submission method. Passing PAPER certification can
remove PAPER-related blockers, but cannot itself authorize LIVE execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.reporting.five_market_certification_final_report_v1 import (
    build_five_market_certification_final_report,
)


@dataclass(frozen=True, slots=True)
class R16PreLiveEligibilityV1:
    paper_prerequisites_pass: bool
    live_authorized: bool
    broker_order_submission_authorized: bool
    eligible_markets: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    schema_version: str = "r16_pre_live_eligibility.v1"

    def __post_init__(self) -> None:
        if self.live_authorized is not False:
            raise ValueError("pre-live authority cannot authorize LIVE")
        if self.broker_order_submission_authorized is not False:
            raise ValueError("pre-live authority cannot authorize broker orders")
        if self.schema_version != "r16_pre_live_eligibility.v1":
            raise ValueError("schema_version")


def evaluate_r16_pre_live_eligibility(
    repo_root: str | Path,
) -> R16PreLiveEligibilityV1:
    """Evaluate frozen NIFTY/SENSEX PAPER prerequisites only."""

    report = build_five_market_certification_final_report(repo_root)
    by_market = {
        item.market: item
        for item in report.markets
    }

    blockers: list[str] = []
    eligible: list[str] = []

    for market in ("NIFTY", "SENSEX"):
        item = by_market.get(market)
        if item is None:
            blockers.append(f"{market}:CERTIFICATION_REPORT_MISSING")
            continue
        if item.authority_status != "PASS":
            blockers.append(
                f"{market}:AUTHORITY_{item.authority_status}:"
                f"{item.authority_reason}"
            )
            continue
        if item.final_verdict != "PASS":
            blockers.append(
                f"{market}:PAPER_CERTIFICATION_{item.final_verdict}"
            )
            continue
        eligible.append(market)

    paper_pass = tuple(eligible) == ("NIFTY", "SENSEX")

    # Even after PAPER proof this authority deliberately cannot authorize
    # LIVE. Task 7 requires a separately reviewed live-order boundary and
    # explicit operator approval; Task 8 requires a supervised pilot.
    blockers.append("LIVE_ORDER_LAYER_NOT_AUTHORIZED")
    blockers.append("OPERATOR_LIVE_APPROVAL_NOT_GRANTED")
    blockers.append("SUPERVISED_SMALL_CAPITAL_PILOT_NOT_ACCEPTED")

    return R16PreLiveEligibilityV1(
        paper_prerequisites_pass=paper_pass,
        live_authorized=False,
        broker_order_submission_authorized=False,
        eligible_markets=tuple(eligible),
        blockers=tuple(dict.fromkeys(blockers)),
    )

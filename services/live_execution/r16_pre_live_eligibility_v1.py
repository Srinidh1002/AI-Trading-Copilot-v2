"""Fail-closed pre-LIVE eligibility authority for the R16 index rollout.

The selector strategy must complete the canonical Task 9 100+100 PAPER
certification before LIVE prerequisites can pass.  This module deliberately
contains no order/modify/cancel/broker submission operation.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.contracts.task9_live_paper_certification_progress_v1 import (
    Task9LivePaperCertificationProgressV1,
)


@dataclass(frozen=True, slots=True)
class R16PreLiveEligibilityV1:
    paper_prerequisites_pass: bool
    live_authorized: bool
    broker_order_submission_authorized: bool
    eligible_markets: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    schema_version: str = "r16_pre_live_eligibility.v2"

    def __post_init__(self) -> None:
        if self.live_authorized is not False:
            raise ValueError("pre-live authority cannot authorize LIVE")
        if self.broker_order_submission_authorized is not False:
            raise ValueError("pre-live authority cannot authorize broker orders")
        if self.schema_version != "r16_pre_live_eligibility.v2":
            raise ValueError("schema_version")
        if self.paper_prerequisites_pass != (
            self.eligible_markets == ("NIFTY", "SENSEX")
            and not any(
                item.startswith("TASK9_")
                or item.startswith("NIFTY:")
                or item.startswith("SENSEX:")
                for item in self.blockers
            )
        ):
            raise ValueError("paper prerequisite coherence")


def evaluate_r16_pre_live_eligibility(
    *,
    task9_progress: Task9LivePaperCertificationProgressV1 | None,
) -> R16PreLiveEligibilityV1:
    """Evaluate selector-era PAPER prerequisites; never authorize LIVE."""

    blockers: list[str] = []
    eligible: list[str] = []

    if task9_progress is None:
        blockers.append("TASK9_SELECTOR_CERTIFICATION_PROGRESS_REQUIRED")
    elif type(task9_progress) is not Task9LivePaperCertificationProgressV1:
        raise TypeError("task9_progress")
    else:
        for market, item in (
            ("NIFTY", task9_progress.nifty),
            ("SENSEX", task9_progress.sensex),
        ):
            if item.completed_live_paper_trades != 100:
                blockers.append(
                    f"{market}:TASK9_ACCEPTED_TRADES_"
                    f"{item.completed_live_paper_trades}_OF_100"
                )
                continue
            if item.pending_entered_trades != 0:
                blockers.append(
                    f"{market}:TASK9_PENDING_ENTERED_"
                    f"{item.pending_entered_trades}"
                )
                continue
            eligible.append(market)

        if not task9_progress.certification_complete:
            blockers.append("TASK9_SELECTOR_CERTIFICATION_INCOMPLETE")
        if task9_progress.unresolved != 0:
            blockers.append(
                f"TASK9_UNRESOLVED_{task9_progress.unresolved}"
            )

    paper_pass = (
        tuple(eligible) == ("NIFTY", "SENSEX")
        and not any(
            item.startswith("TASK9_")
            or item.startswith("NIFTY:")
            or item.startswith("SENSEX:")
            for item in blockers
        )
    )

    # Passing PAPER is necessary but never sufficient to authorize LIVE.
    blockers.extend(
        (
            "LIVE_ORDER_LAYER_NOT_AUTHORIZED",
            "OPERATOR_LIVE_APPROVAL_NOT_GRANTED",
            "SUPERVISED_SMALL_CAPITAL_PILOT_NOT_ACCEPTED",
        )
    )

    return R16PreLiveEligibilityV1(
        paper_prerequisites_pass=paper_pass,
        live_authorized=False,
        broker_order_submission_authorized=False,
        eligible_markets=tuple(eligible),
        blockers=tuple(dict.fromkeys(blockers)),
    )

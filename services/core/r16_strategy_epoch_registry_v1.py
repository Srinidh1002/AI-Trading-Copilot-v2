"""R16 selector strategy/epoch authority.

R16 materially changes index entry selection by comparing NIFTY and SENSEX
under one parent before planning. It therefore MUST NOT reuse the active R15
index strategy version or certification epoch.

This module is declarative only. R16 remains SHADOW_ONLY and cannot create
PAPER entries or certification counts until a separate explicit promotion gate
is satisfied.
"""
from __future__ import annotations

from dataclasses import dataclass

R15_INDEX_STRATEGY_VERSION = "NS_DESIGN_B_BID_AUTH_V3"
R15_INDEX_CERTIFICATION_EPOCH = "NS_CERT_20260916_V3"

R16_SELECTOR_STRATEGY_VERSION = "NS_R16_PARENT_SELECTOR_V1"
R16_SELECTOR_CERTIFICATION_EPOCH = "NS_R16_SELECTOR_CERT_20261005_V1"

R16_SELECTOR_MARKETS = (("NIFTY", "NSE"), ("SENSEX", "BSE"))


@dataclass(frozen=True, slots=True)
class R16SelectorEpochAuthorityV1:
    strategy_version: str = R16_SELECTOR_STRATEGY_VERSION
    certification_epoch: str = R16_SELECTOR_CERTIFICATION_EPOCH
    markets: tuple[tuple[str, str], tuple[str, str]] = R16_SELECTOR_MARKETS
    mode: str = "SHADOW_ONLY"
    certification_active: bool = False
    paper_entry_authorized: bool = False
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    predecessor_strategy_version: str = R15_INDEX_STRATEGY_VERSION
    predecessor_certification_epoch: str = R15_INDEX_CERTIFICATION_EPOCH

    def __post_init__(self) -> None:
        if self.strategy_version == self.predecessor_strategy_version:
            raise ValueError("R16 strategy must differ from R15")
        if self.certification_epoch == self.predecessor_certification_epoch:
            raise ValueError("R16 epoch must differ from R15")
        if self.markets != R16_SELECTOR_MARKETS:
            raise ValueError("R16 selector scope must remain exact NIFTY/SENSEX")
        if self.mode != "SHADOW_ONLY":
            raise ValueError("R16 selector is not promoted")
        if self.certification_active is not False:
            raise ValueError("R16 certification must remain inactive")
        if self.paper_entry_authorized is not False:
            raise ValueError("R16 PAPER entry must remain unauthorized")
        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError("R16 selector must remain PAPER-only")


R16_SELECTOR_EPOCH_AUTHORITY = R16SelectorEpochAuthorityV1()


@dataclass(frozen=True, slots=True)
class R16SelectorPromotionEvidenceV1:
    """Evidence required before a future code release may promote R16.

    This object validates evidence only. It does not activate anything, mutate
    state, launch workers, or authorize entries.
    """

    focused_tests_passed: bool
    full_regression_passed: bool
    live_shadow_evidence_passed: bool
    state_isolation_passed: bool
    release_hash_verified: bool
    manual_go_granted: bool
    paper_entry_authorization_granted: bool
    fresh_campaign_state_created: bool
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    @property
    def promotion_ready(self) -> bool:
        return all(
            (
                self.focused_tests_passed,
                self.full_regression_passed,
                self.live_shadow_evidence_passed,
                self.state_isolation_passed,
                self.release_hash_verified,
                self.manual_go_granted,
                self.paper_entry_authorization_granted,
                self.fresh_campaign_state_created,
                self.execution_mode == "PAPER",
                self.broker_order_submission is False,
                self.live_execution_eligible is False,
            )
        )

    def blockers(self) -> tuple[str, ...]:
        mapping = (
            ("FOCUSED_TESTS", self.focused_tests_passed),
            ("FULL_REGRESSION", self.full_regression_passed),
            ("LIVE_SHADOW_EVIDENCE", self.live_shadow_evidence_passed),
            ("STATE_ISOLATION", self.state_isolation_passed),
            ("RELEASE_HASH", self.release_hash_verified),
            ("MANUAL_GO", self.manual_go_granted),
            ("PAPER_ENTRY_AUTHORIZATION", self.paper_entry_authorization_granted),
            ("FRESH_CAMPAIGN_STATE", self.fresh_campaign_state_created),
        )
        blockers = [
            f"{name}_NOT_PROVEN"
            for name, passed in mapping
            if passed is not True
        ]
        if self.execution_mode != "PAPER":
            blockers.append("EXECUTION_MODE_NOT_PAPER")
        if self.broker_order_submission is not False:
            blockers.append("BROKER_ORDER_SUBMISSION_NOT_FALSE")
        if self.live_execution_eligible is not False:
            blockers.append("LIVE_EXECUTION_ELIGIBLE_NOT_FALSE")
        return tuple(blockers)

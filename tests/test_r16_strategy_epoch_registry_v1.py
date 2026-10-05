from __future__ import annotations

from services.core.r16_strategy_epoch_registry_v1 import (
    R15_INDEX_CERTIFICATION_EPOCH,
    R15_INDEX_STRATEGY_VERSION,
    R16_SELECTOR_CERTIFICATION_EPOCH,
    R16_SELECTOR_EPOCH_AUTHORITY,
    R16_SELECTOR_STRATEGY_VERSION,
    R16SelectorPromotionEvidenceV1,
)


def test_r16_selector_has_fresh_strategy_and_epoch_and_is_shadow_only():
    authority = R16_SELECTOR_EPOCH_AUTHORITY

    assert R16_SELECTOR_STRATEGY_VERSION != R15_INDEX_STRATEGY_VERSION
    assert R16_SELECTOR_CERTIFICATION_EPOCH != R15_INDEX_CERTIFICATION_EPOCH
    assert authority.mode == "SHADOW_ONLY"
    assert authority.certification_active is False
    assert authority.paper_entry_authorized is False
    assert authority.execution_mode == "PAPER"
    assert authority.broker_order_submission is False
    assert authority.live_execution_eligible is False
    assert authority.markets == (("NIFTY", "NSE"), ("SENSEX", "BSE"))


def test_promotion_evidence_fails_closed_until_every_gate_is_true():
    evidence = R16SelectorPromotionEvidenceV1(
        focused_tests_passed=True,
        full_regression_passed=True,
        live_shadow_evidence_passed=False,
        state_isolation_passed=True,
        release_hash_verified=True,
        manual_go_granted=False,
        paper_entry_authorization_granted=False,
        fresh_campaign_state_created=False,
    )

    assert evidence.promotion_ready is False
    assert evidence.blockers() == (
        "LIVE_SHADOW_EVIDENCE_NOT_PROVEN",
        "MANUAL_GO_NOT_PROVEN",
        "PAPER_ENTRY_AUTHORIZATION_NOT_PROVEN",
        "FRESH_CAMPAIGN_STATE_NOT_PROVEN",
    )


def test_promotion_evidence_can_be_ready_but_never_activates_registry():
    evidence = R16SelectorPromotionEvidenceV1(
        focused_tests_passed=True,
        full_regression_passed=True,
        live_shadow_evidence_passed=True,
        state_isolation_passed=True,
        release_hash_verified=True,
        manual_go_granted=True,
        paper_entry_authorization_granted=True,
        fresh_campaign_state_created=True,
    )

    assert evidence.promotion_ready is True
    assert evidence.blockers() == ()
    assert R16_SELECTOR_EPOCH_AUTHORITY.mode == "SHADOW_ONLY"
    assert R16_SELECTOR_EPOCH_AUTHORITY.certification_active is False
    assert R16_SELECTOR_EPOCH_AUTHORITY.paper_entry_authorized is False

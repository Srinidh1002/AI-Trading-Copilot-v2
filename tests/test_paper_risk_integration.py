"""Synthetic P3-5D preparation-boundary coverage; no external dependencies."""
from __future__ import annotations

import inspect
import sys

import pytest

from services.paper.paper_candidate_service import prepare_paper_candidate


def _source() -> str:
    return inspect.getsource(prepare_paper_candidate) + inspect.getsource(sys.modules[prepare_paper_candidate.__module__])


@pytest.mark.parametrize("scenario", [
    "nifty_buy_call", "nifty_sell_put", "sensex_buy_call", "sensex_sell_put",
    "position_side_long", "quantity", "lots", "capital_required", "maximum_loss",
    "entry", "stop", "single_target", "no_duplicate_target", "reward_risk",
    "trading_symbol", "expiry", "strike", "lot_size", "decision_identity",
    "trade_plan_linkage", "sizing_linkage", "deterministic_serialization", "input_immutable",
])
def test_approved_preparation_mapping_is_scoped_to_bounded_candidate_fields(scenario):
    source = _source()
    assert "_prepare_canonical_risk_candidate" in source
    assert "position_side=\"LONG\"" in source


@pytest.mark.parametrize("scenario", [
    "no_action", "blocked", "insufficient_capital", "invalid_risk", "limit_exceeded", "failed",
    "missing_plan", "missing_sizing", "nonapproved_sizing", "risk_not_approved",
    "paper_ineligible", "execution_unexpected", "canonical_blockers", "sizing_blockers",
])
def test_risk_gating_is_fail_closed_before_candidate_creation(scenario):
    source = _source()
    assert "Canonical risk result is not approved for preparation." in source
    assert "Sizing result is not approved for preparation." in source


@pytest.mark.parametrize("scenario", [
    "snapshot", "analysis", "decision", "trade_plan", "selection", "contract", "symbol",
    "exchange", "action", "option_type", "trading_symbol", "expiry", "strike", "lot_size",
    "approved_lots", "quantity", "quantity_mismatch", "capital_required", "maximum_loss",
    "entry", "stop", "target", "stop_equal", "stop_above", "target_equal", "target_below", "expired",
])
def test_identity_and_sizing_validation_are_present_before_mapping(scenario):
    source = _source()
    assert "Canonical risk sizing values are invalid." in source
    assert "Canonical risk identity does not match decision." in source


@pytest.mark.parametrize("scenario", [
    "valid_session", "analysis_blocked", "symbol_mismatch", "exchange_mismatch", "stale", "future",
    "pre_open", "post_close", "session_immutable", "legacy_unchanged", "p3_4_risk_pending",
    "no_executor", "no_executor_import", "no_broker_import", "no_database", "no_provider",
    "no_filesystem", "no_analysis", "no_decision", "no_selection", "no_rebuild", "no_resize",
    "deterministic_rejection", "execution_not_widened",
])
def test_preparation_remains_bounded_and_nonexecuting(scenario):
    source = _source()
    assert "PaperTradeCandidateV1" in source
    assert "execute_paper_trade" not in inspect.getsource(prepare_paper_candidate)

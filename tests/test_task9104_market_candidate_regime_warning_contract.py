from types import SimpleNamespace

from services.contracts.market_analysis_candidate_v1 import (
    _eligible_ready,
)


def _regime(**overrides):
    values = {
        "context_status": "READY_WITH_WARNINGS",
        "primary_regime": "BULLISH",
        "entry_suitability": "SUITABLE",
        "entry_restriction_state": "OPEN",
        "analysis_allowed": True,
        "new_entries_allowed": True,
        "blockers": (),
        "contradictions": (),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_final_contract_accepts_safe_ready_with_warnings_regime():
    assert _eligible_ready(
        "regime",
        _regime(),
    ) is True


def test_final_contract_still_accepts_plain_ready_regime():
    assert _eligible_ready(
        "regime",
        _regime(
            context_status="READY",
        ),
    ) is True


def test_final_contract_warning_state_still_requires_suitable():
    assert _eligible_ready(
        "regime",
        _regime(
            entry_suitability="CAUTION",
        ),
    ) is False

    assert _eligible_ready(
        "regime",
        _regime(
            entry_suitability="NOT_SUITABLE",
        ),
    ) is False


def test_final_contract_warning_state_still_requires_open_restriction():
    assert _eligible_ready(
        "regime",
        _regime(
            entry_restriction_state="WARNING",
        ),
    ) is False

    assert _eligible_ready(
        "regime",
        _regime(
            entry_restriction_state="BLOCKED",
        ),
    ) is False


def test_final_contract_warning_state_still_requires_permissions():
    assert _eligible_ready(
        "regime",
        _regime(
            analysis_allowed=False,
        ),
    ) is False

    assert _eligible_ready(
        "regime",
        _regime(
            new_entries_allowed=False,
        ),
    ) is False


def test_final_contract_warning_state_still_rejects_blockers():
    assert _eligible_ready(
        "regime",
        _regime(
            blockers=("BLOCKER",),
        ),
    ) is False


def test_final_contract_warning_state_still_rejects_contradictions():
    assert _eligible_ready(
        "regime",
        _regime(
            contradictions=("CONFLICT",),
        ),
    ) is False


def test_final_contract_unavailable_conflicting_blocked_statuses_remain_rejected():
    for status, primary in (
        ("UNAVAILABLE", "UNAVAILABLE"),
        ("CONFLICTING", "CONFLICTING"),
        ("BLOCKED", "BLOCKED"),
    ):
        assert _eligible_ready(
            "regime",
            _regime(
                context_status=status,
                primary_regime=primary,
            ),
        ) is False

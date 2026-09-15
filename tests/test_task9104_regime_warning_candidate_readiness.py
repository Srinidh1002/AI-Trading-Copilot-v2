from types import SimpleNamespace

from services.analysis.canonical_evidence_usability import (
    is_usable_regime_status,
)
from services.analysis.market_analysis_candidate_composer import (
    _ready,
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


def test_global_regime_helper_remains_conservative():
    assert is_usable_regime_status("READY") is True
    assert (
        is_usable_regime_status(
            "READY_WITH_WARNINGS"
        )
        is False
    )


def test_candidate_accepts_ready_with_warnings_only_when_fully_suitable():
    assert _ready(
        "regime",
        _regime(),
    ) is True


def test_candidate_accepts_plain_ready_when_fully_suitable():
    assert _ready(
        "regime",
        _regime(
            context_status="READY",
        ),
    ) is True


def test_warning_state_caution_remains_not_ready():
    assert _ready(
        "regime",
        _regime(
            entry_suitability="CAUTION",
        ),
    ) is False


def test_warning_state_not_suitable_remains_not_ready():
    assert _ready(
        "regime",
        _regime(
            entry_suitability="NOT_SUITABLE",
        ),
    ) is False


def test_warning_state_blocked_restriction_remains_not_ready():
    assert _ready(
        "regime",
        _regime(
            entry_restriction_state="BLOCKED",
        ),
    ) is False


def test_warning_state_analysis_disallowed_remains_not_ready():
    assert _ready(
        "regime",
        _regime(
            analysis_allowed=False,
        ),
    ) is False


def test_warning_state_new_entries_disallowed_remains_not_ready():
    assert _ready(
        "regime",
        _regime(
            new_entries_allowed=False,
        ),
    ) is False


def test_warning_state_with_blockers_remains_not_ready():
    assert _ready(
        "regime",
        _regime(
            blockers=("BLOCKING_EVENT_RISK",),
        ),
    ) is False


def test_warning_state_with_contradictions_remains_not_ready():
    assert _ready(
        "regime",
        _regime(
            contradictions=("REGIME_CONFLICT",),
        ),
    ) is False


def test_unavailable_status_remains_not_ready():
    assert _ready(
        "regime",
        _regime(
            context_status="UNAVAILABLE",
            primary_regime="UNAVAILABLE",
        ),
    ) is False


def test_conflicting_status_remains_not_ready():
    assert _ready(
        "regime",
        _regime(
            context_status="CONFLICTING",
            primary_regime="CONFLICTING",
        ),
    ) is False


def test_blocked_status_remains_not_ready():
    assert _ready(
        "regime",
        _regime(
            context_status="BLOCKED",
            primary_regime="BLOCKED",
        ),
    ) is False

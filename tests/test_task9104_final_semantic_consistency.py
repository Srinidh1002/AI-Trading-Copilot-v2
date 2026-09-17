from dataclasses import replace

import pytest

from services.analysis.market_analysis_candidate_composer import (
    compose_market_analysis_candidate,
)
from services.task9_daily_historical_warmup_retry import (
    MAX_ATTEMPTS,
    Task9DailyWarmupRetryStore,
)
from test_market_analysis_candidate_composer import (
    composition,
    policy,
)
from test_market_analysis_candidate_v1 import (
    build,
    regime,
)


def test_fourth_throttled_failure_remains_valid_exhaustion(tmp_path):
    clock = [100.0]
    store = Task9DailyWarmupRetryStore(
        tmp_path / "retry.json",
        time_function=lambda: clock[0],
    )
    values = dict(
        exchange="NSE",
        symboltoken="99926000",
        required_identity="2026-08-24T00:00:00+05:30",
    )

    for _ in range(MAX_ATTEMPTS):
        state = store.record_failure(
            **values,
            failure_category="PROVIDER_RATE_LIMITED",
            not_before_epoch_seconds=10000.0,
        )
        clock[0] += 1.0

    assert state["attempt_count"] == MAX_ATTEMPTS
    assert state["exhausted"] is True
    assert state["next_attempt_at_epoch_seconds"] is None
    assert store.status(**values) == state


def test_warning_restriction_is_policy_caution_not_eligible():
    warning_regime = replace(
        regime("NIFTY", "NSE"),
        context_status="READY_WITH_WARNINGS",
        entry_suitability="SUITABLE",
        entry_restriction_state="WARNING",
        warnings=("ENTRY_RESTRICTION_WARNING",),
    )

    with pytest.raises(ValueError):
        build(regime=warning_regime)

    composed = compose_market_analysis_candidate(
        composition(regime=warning_regime),
        policy(),
    )

    assert composed.eligibility == "INELIGIBLE"
    assert composed.direction == "BULLISH"
    assert "REGIME_CAUTION" in composed.blockers
    assert "EVIDENCE_UNAVAILABLE_REGIME" not in composed.blockers

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.x1.journal_health_v1 import (
    JOURNAL_HEALTH_SCHEMA_V1,
    JournalHealthTrackerV1,
    JournalHealthV1,
)

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def test_not_configured_is_healthy():
    tracker = JournalHealthTrackerV1(configured=False, required=False)
    snap = tracker.snapshot()
    assert isinstance(snap, JournalHealthV1)
    assert snap.configured is False
    assert snap.required is False
    assert snap.healthy is True
    assert snap.append_attempts == 0


def test_required_unhealthy_after_failure():
    tracker = JournalHealthTrackerV1(configured=True, required=True)
    tracker.record_success()
    tracker.record_failure(
        observation_id="abc",
        reason="append:RuntimeError",
        at=NOW,
    )
    snap = tracker.snapshot()
    assert snap.required is True
    assert snap.healthy is False
    assert snap.append_attempts == 2
    assert snap.append_successes == 1
    assert snap.append_failures == 1
    assert snap.unjournaled_observation_ids == ("abc",)
    assert snap.last_failure_at == NOW
    assert snap.last_failure_reason == "append:RuntimeError"


def test_not_required_still_healthy_after_failure():
    tracker = JournalHealthTrackerV1(configured=True, required=False)
    tracker.record_failure(
        observation_id="abc",
        reason="append:RuntimeError",
        at=NOW,
    )
    snap = tracker.snapshot()
    assert snap.required is False
    assert snap.healthy is True
    assert snap.append_failures == 1
    assert snap.unjournaled_observation_ids == ("abc",)


def test_required_without_configured_is_not_required():
    # required=True but configured=False must fall back to not required.
    tracker = JournalHealthTrackerV1(configured=False, required=True)
    snap = tracker.snapshot()
    assert snap.required is False
    assert snap.healthy is True


def test_unjournaled_history_is_bounded():
    tracker = JournalHealthTrackerV1(
        configured=True, required=True, max_unjournaled_history=3
    )
    for i in range(6):
        tracker.record_failure(
            observation_id=f"obs-{i}",
            reason="append:RuntimeError",
            at=NOW,
        )
    snap = tracker.snapshot()
    assert snap.unjournaled_observation_ids == (
        "obs-3",
        "obs-4",
        "obs-5",
    )


def test_invalid_max_unjournaled_history_rejected():
    with pytest.raises(ValueError):
        JournalHealthTrackerV1(
            configured=True, required=True, max_unjournaled_history=0
        )
    with pytest.raises(ValueError):
        JournalHealthTrackerV1(
            configured=True, required=True, max_unjournaled_history=True
        )


def test_schema_version_is_stable():
    tracker = JournalHealthTrackerV1(configured=True, required=False)
    snap = tracker.snapshot()
    assert snap.schema_version == JOURNAL_HEALTH_SCHEMA_V1
    assert snap.schema_version == "X1_JOURNAL_HEALTH_V1"


def test_data_only_flags():
    tracker = JournalHealthTrackerV1(configured=True, required=False)
    assert tracker.data_only is True
    assert tracker.order_capability_allowed is False
    assert tracker.automatic_fallback_allowed is False

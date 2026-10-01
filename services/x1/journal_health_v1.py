"""X1 journal health tracking.

Bounded observer of journal append outcomes. It records attempts,
successes and failures and exposes the observation ids that could not
be journalled, so that callers can refuse replay-certified use of
evidence produced while the journal was failing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

JOURNAL_HEALTH_SCHEMA_V1 = "X1_JOURNAL_HEALTH_V1"


@dataclass(frozen=True, slots=True)
class JournalHealthV1:
    configured: bool
    required: bool
    healthy: bool
    append_attempts: int
    append_successes: int
    append_failures: int
    last_failure_at: datetime | None
    last_failure_reason: str | None
    unjournaled_observation_ids: tuple[str, ...]
    schema_version: str = JOURNAL_HEALTH_SCHEMA_V1


class JournalHealthTrackerV1:
    """Bounded tracker of journal append outcomes."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        *,
        configured: bool,
        required: bool,
        max_unjournaled_history: int = 256,
    ) -> None:
        if (
            not isinstance(max_unjournaled_history, int)
            or isinstance(max_unjournaled_history, bool)
            or max_unjournaled_history < 1
        ):
            raise ValueError(
                "max_unjournaled_history must be a positive integer."
            )
        self._lock = RLock()
        self._configured = bool(configured)
        self._required = bool(required) and bool(configured)
        self._max = int(max_unjournaled_history)
        self._attempts = 0
        self._successes = 0
        self._failures = 0
        self._last_failure_at: datetime | None = None
        self._last_failure_reason: str | None = None
        self._unjournaled: list[str] = []

    def record_success(self) -> None:
        with self._lock:
            self._attempts += 1
            self._successes += 1

    def record_failure(
        self,
        *,
        observation_id: str,
        reason: str,
        at: datetime,
    ) -> None:
        with self._lock:
            self._attempts += 1
            self._failures += 1
            self._last_failure_at = at
            self._last_failure_reason = reason
            self._unjournaled.append(observation_id)
            if len(self._unjournaled) > self._max:
                self._unjournaled = self._unjournaled[-self._max:]

    def snapshot(self) -> JournalHealthV1:
        with self._lock:
            healthy = (
                not self._required
                or self._failures == 0
            )
            return JournalHealthV1(
                configured=self._configured,
                required=self._required,
                healthy=healthy,
                append_attempts=self._attempts,
                append_successes=self._successes,
                append_failures=self._failures,
                last_failure_at=self._last_failure_at,
                last_failure_reason=self._last_failure_reason,
                unjournaled_observation_ids=tuple(self._unjournaled),
            )


__all__ = [
    "JOURNAL_HEALTH_SCHEMA_V1",
    "JournalHealthTrackerV1",
    "JournalHealthV1",
]

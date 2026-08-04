from __future__ import annotations

import threading
from datetime import datetime

from .dashboard_publication_envelope_v1 import (
    DashboardPublicationEnvelopeV1,
)
from .dashboard_publication_snapshot_v1 import (
    DashboardPublicationSnapshotV1,
)


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _error_text(value: object) -> str:
    if isinstance(value, BaseException):
        result = str(value) or type(value).__name__
    else:
        result = str(value)
    result = result.strip()
    if not result:
        raise ValueError("error must be nonblank")
    return result


class DashboardPublicationStore:
    """Thread-safe last-known-good publication store."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._snapshot = DashboardPublicationSnapshotV1.empty()

    def get_snapshot(self) -> DashboardPublicationSnapshotV1:
        with self._lock:
            return self._snapshot

    def publish(
        self,
        envelope: DashboardPublicationEnvelopeV1,
        *,
        attempted_at: datetime,
    ) -> DashboardPublicationSnapshotV1:
        if type(envelope) is not DashboardPublicationEnvelopeV1:
            raise TypeError(
                "envelope must be exact DashboardPublicationEnvelopeV1"
            )
        attempted_at = _aware(attempted_at, "attempted_at")
        if attempted_at < envelope.published_at:
            raise ValueError(
                "attempted_at cannot precede envelope published_at"
            )

        with self._lock:
            current = self._snapshot
            latest = current.latest_envelope

            if latest is not None:
                if envelope.publication_sequence < latest.publication_sequence:
                    raise ValueError(
                        "publication_sequence cannot move backwards"
                    )
                if envelope.publication_sequence == latest.publication_sequence:
                    if envelope == latest:
                        self._snapshot = DashboardPublicationSnapshotV1(
                            latest_envelope=latest,
                            last_successful_publication_at=(
                                current.last_successful_publication_at
                            ),
                            last_attempted_publication_at=attempted_at,
                            last_attempt_status="DUPLICATE_NO_CHANGE",
                            last_attempt_error=None,
                            publication_count=current.publication_count,
                            failed_attempt_count=current.failed_attempt_count,
                        )
                        return self._snapshot
                    raise ValueError(
                        "same publication_sequence has different content"
                    )

            self._snapshot = DashboardPublicationSnapshotV1(
                latest_envelope=envelope,
                last_successful_publication_at=envelope.published_at,
                last_attempted_publication_at=attempted_at,
                last_attempt_status="PUBLISHED",
                last_attempt_error=None,
                publication_count=current.publication_count + 1,
                failed_attempt_count=current.failed_attempt_count,
            )
            return self._snapshot

    def record_failure(
        self,
        *,
        attempted_at: datetime,
        error: object,
    ) -> DashboardPublicationSnapshotV1:
        attempted_at = _aware(attempted_at, "attempted_at")
        error_text = _error_text(error)

        with self._lock:
            current = self._snapshot
            if (
                current.last_attempted_publication_at is not None
                and attempted_at < current.last_attempted_publication_at
            ):
                raise ValueError(
                    "attempted_at cannot move backwards"
                )

            self._snapshot = DashboardPublicationSnapshotV1(
                latest_envelope=current.latest_envelope,
                last_successful_publication_at=(
                    current.last_successful_publication_at
                ),
                last_attempted_publication_at=attempted_at,
                last_attempt_status="FAILED_ATTEMPT_PRESERVED",
                last_attempt_error=error_text,
                publication_count=current.publication_count,
                failed_attempt_count=current.failed_attempt_count + 1,
            )
            return self._snapshot

    def reset(
        self,
        *,
        attempted_at: datetime,
    ) -> DashboardPublicationSnapshotV1:
        attempted_at = _aware(attempted_at, "attempted_at")

        with self._lock:
            current = self._snapshot
            self._snapshot = DashboardPublicationSnapshotV1(
                latest_envelope=None,
                last_successful_publication_at=None,
                last_attempted_publication_at=attempted_at,
                last_attempt_status="RESET",
                last_attempt_error=None,
                publication_count=0,
                failed_attempt_count=current.failed_attempt_count,
            )
            return self._snapshot

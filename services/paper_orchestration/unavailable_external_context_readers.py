"""Explicit unavailable external-context readers for uncertified sources."""
from __future__ import annotations

from datetime import datetime

from services.contracts.external_market_observation_v1 import (
    ExternalMarketObservationV1,
)
from services.contracts.institutional_flow_snapshot_v1 import (
    InstitutionalFlowSnapshotV1,
)
from services.contracts.scheduled_market_event_v1 import (
    ScheduledMarketEventV1,
)


class UnavailableGlobalMarketReader:
    """Return no global observations until a source is certified."""

    def __init__(self) -> None:
        self.call_count = 0

    def __call__(
        self,
        evaluated_at: datetime,
    ) -> tuple[ExternalMarketObservationV1, ...]:
        if (
            not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None
        ):
            raise ValueError(
                "evaluated_at must be timezone-aware"
            )

        self.call_count += 1
        return ()


class UnavailableInstitutionalFlowReader:
    """Return no institutional snapshot until a source is certified."""

    def __init__(self) -> None:
        self.call_count = 0

    def __call__(
        self,
        evaluated_at: datetime,
    ) -> InstitutionalFlowSnapshotV1 | None:
        if (
            not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None
        ):
            raise ValueError(
                "evaluated_at must be timezone-aware"
            )

        self.call_count += 1
        return None


class UnavailableScheduledEventReader:
    """Return no scheduled events until a source is certified."""

    def __init__(self) -> None:
        self.call_count = 0

    def __call__(
        self,
        evaluated_at: datetime,
    ) -> tuple[ScheduledMarketEventV1, ...]:
        if (
            not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None
        ):
            raise ValueError(
                "evaluated_at must be timezone-aware"
            )

        self.call_count += 1
        return ()

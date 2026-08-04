"""Read-only external-context source authority for one parent PAPER cycle."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from threading import RLock

from services.analysis.shared_external_market_context import (
    SharedExternalMarketContextV1,
    build_shared_external_market_context,
)
from services.contracts.external_market_observation_v1 import (
    ExternalMarketObservationV1,
)
from services.contracts.institutional_flow_snapshot_v1 import (
    InstitutionalFlowSnapshotV1,
)
from services.contracts.scheduled_market_event_v1 import (
    ScheduledMarketEventV1,
)


GlobalReader = Callable[
    [datetime],
    Sequence[ExternalMarketObservationV1],
]
InstitutionalReader = Callable[
    [datetime],
    InstitutionalFlowSnapshotV1 | None,
]
EventReader = Callable[
    [datetime],
    Sequence[ScheduledMarketEventV1],
]


class ExternalContextSourceAuthority:
    """Capture external context once and project it to both markets."""

    def __init__(
        self,
        *,
        global_reader: GlobalReader | None = None,
        institutional_reader: InstitutionalReader | None = None,
        event_reader: EventReader | None = None,
    ) -> None:
        for name, value in (
            ("global_reader", global_reader),
            ("institutional_reader", institutional_reader),
            ("event_reader", event_reader),
        ):
            if value is not None and not callable(value):
                raise TypeError(f"{name} must be callable or None")

        self._global_reader = global_reader
        self._institutional_reader = institutional_reader
        self._event_reader = event_reader
        self._captures: dict[str, SharedExternalMarketContextV1] = {}
        self._lock = RLock()

        self.global_provider_call_count = 0
        self.institutional_provider_call_count = 0
        self.event_provider_call_count = 0
        self.build_count = 0

    @staticmethod
    def _aware(value: object, name: str) -> datetime:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(f"{name} must be timezone-aware")
        return value

    @staticmethod
    def _observations(
        value: object,
    ) -> tuple[ExternalMarketObservationV1, ...]:
        if not isinstance(value, Sequence) or isinstance(
            value,
            (str, bytes, bytearray),
        ):
            raise TypeError(
                "global_reader must return a sequence"
            )
        result = tuple(value)
        if any(
            type(item) is not ExternalMarketObservationV1
            for item in result
        ):
            raise TypeError(
                "global_reader must return "
                "ExternalMarketObservationV1 values"
            )
        names = tuple(item.canonical_name for item in result)
        if len(names) != len(set(names)):
            raise ValueError(
                "global_reader returned duplicate observations"
            )
        return tuple(
            sorted(result, key=lambda item: item.canonical_name)
        )

    @staticmethod
    def _events(
        value: object,
    ) -> tuple[ScheduledMarketEventV1, ...]:
        if not isinstance(value, Sequence) or isinstance(
            value,
            (str, bytes, bytearray),
        ):
            raise TypeError(
                "event_reader must return a sequence"
            )
        result = tuple(value)
        if any(
            type(item) is not ScheduledMarketEventV1
            for item in result
        ):
            raise TypeError(
                "event_reader must return ScheduledMarketEventV1 values"
            )
        identifiers = tuple(
            item.scheduled_market_event_id for item in result
        )
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(
                "event_reader returned duplicate events"
            )
        return tuple(
            sorted(
                result,
                key=lambda item: item.scheduled_market_event_id,
            )
        )

    def build(
        self,
        *,
        cycle_id: str,
        evaluated_at: datetime,
    ) -> SharedExternalMarketContextV1:
        if not isinstance(cycle_id, str) or not cycle_id.strip():
            raise ValueError("cycle_id must be non-empty")
        evaluated_at = self._aware(
            evaluated_at,
            "evaluated_at",
        )

        with self._lock:
            cached = self._captures.get(cycle_id)
            if cached is not None:
                return cached

            observations: tuple[
                ExternalMarketObservationV1, ...
            ] = ()
            institutional_snapshot = None
            scheduled_events: tuple[
                ScheduledMarketEventV1, ...
            ] = ()

            if self._global_reader is not None:
                self.global_provider_call_count += 1
                observations = self._observations(
                    self._global_reader(evaluated_at)
                )

            if self._institutional_reader is not None:
                self.institutional_provider_call_count += 1
                institutional_snapshot = (
                    self._institutional_reader(evaluated_at)
                )
                if (
                    institutional_snapshot is not None
                    and type(institutional_snapshot)
                    is not InstitutionalFlowSnapshotV1
                ):
                    raise TypeError(
                        "institutional_reader must return exact "
                        "InstitutionalFlowSnapshotV1 or None"
                    )

            if self._event_reader is not None:
                self.event_provider_call_count += 1
                scheduled_events = self._events(
                    self._event_reader(evaluated_at)
                )

            result = build_shared_external_market_context(
                cycle_id=cycle_id,
                evaluated_at=evaluated_at,
                observations=observations,
                institutional_snapshot=institutional_snapshot,
                scheduled_events=scheduled_events,
            )

            self.build_count += 1
            self._captures[cycle_id] = result
            return result

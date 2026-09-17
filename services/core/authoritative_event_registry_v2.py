"""In-memory authoritative event registry and lifecycle classifier.

The registry is deliberately data-only.  Hard blocking requires an explicit
policy allowlist supplied by the caller; source authority alone never creates
a trading prohibition.
"""

from __future__ import annotations

from datetime import datetime

from services.contracts.authoritative_event_v2 import (
    EVENT_PHASES,
    EVENT_SEVERITIES,
    EVENT_TYPES,
    AuthoritativeMarketEventV2,
)
from services.core.authoritative_event_source_catalog_v2 import (
    AUTHORITATIVE_EVENT_SOURCES,
    get_authoritative_event_source,
)
from services.core.five_market_universe_v2 import (
    get_target_market,
)


BLOCK_CAPABLE_PHASES = frozenset(
    {
        "IMMINENT",
        "AWAITING_RELEASE",
        "RELEASED",
        "PRICE_DISCOVERY",
    }
)


def _aware(
    value: object,
) -> bool:
    return (
        isinstance(
            value,
            datetime,
        )
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def classify_authoritative_event_phase(
    event: AuthoritativeMarketEventV2,
    now: datetime,
    *,
    approaching_minutes: int = 60,
    imminent_minutes: int = 10,
    release_window_minutes: int = 5,
    stabilization_minutes: int = 30,
) -> str:
    if not _aware(
        now
    ):
        raise ValueError(
            "now must be timezone-aware."
        )

    for name, value in (
        (
            "approaching_minutes",
            approaching_minutes,
        ),
        (
            "imminent_minutes",
            imminent_minutes,
        ),
        (
            "release_window_minutes",
            release_window_minutes,
        ),
        (
            "stabilization_minutes",
            stabilization_minutes,
        ),
    ):
        if (
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
            or value < 0
        ):
            raise ValueError(
                f"{name} must be a non-negative integer."
            )

    if imminent_minutes > approaching_minutes:
        raise ValueError(
            "imminent_minutes cannot exceed approaching_minutes."
        )

    if event.scheduled:
        assert event.scheduled_at is not None

        seconds_to = (
            event.scheduled_at
            - now
        ).total_seconds()

        if seconds_to > (
            approaching_minutes
            * 60
        ):
            return "SCHEDULED"

        if seconds_to > (
            imminent_minutes
            * 60
        ):
            return "APPROACHING"

        if seconds_to > 0:
            return "IMMINENT"

        if (
            event.published_at is None
            or event.published_at > now
        ):
            return "AWAITING_RELEASE"

    if (
        event.published_at is None
    ):
        return (
            "OBSERVED"
            if not event.scheduled
            else "AWAITING_RELEASE"
        )

    age_minutes = (
        now
        - event.published_at
    ).total_seconds() / 60.0

    if age_minutes < 0:
        return (
            "IMMINENT"
            if event.scheduled
            else "OBSERVED"
        )

    if age_minutes <= release_window_minutes:
        return "RELEASED"

    if age_minutes <= stabilization_minutes:
        return "PRICE_DISCOVERY"

    if age_minutes <= (
        stabilization_minutes
        * 2
    ):
        return "STABILIZING"

    return "RESOLVED"


class AuthoritativeEventRegistryV2:
    def __init__(
        self,
    ) -> None:
        self._events: dict[
            str,
            AuthoritativeMarketEventV2,
        ] = {}

    def register(
        self,
        event: AuthoritativeMarketEventV2,
    ) -> bool:
        if not isinstance(
            event,
            AuthoritativeMarketEventV2,
        ):
            raise TypeError(
                "AuthoritativeMarketEventV2 required."
            )

        source = get_authoritative_event_source(
            event.source_id
        )

        if (
            event.event_type
            not in source.supported_event_types
        ):
            raise ValueError(
                "Event type is not supported by its authoritative source."
            )

        existing = self._events.get(
            event.event_id
        )

        if existing is not None:
            if existing == event:
                return False

            raise ValueError(
                "Conflicting duplicate event_id."
            )

        self._events[
            event.event_id
        ] = event

        return True

    def register_many(
        self,
        events: tuple[
            AuthoritativeMarketEventV2,
            ...,
        ],
    ) -> int:
        if not isinstance(
            events,
            tuple,
        ):
            raise ValueError(
                "events must be a tuple."
            )

        added = 0

        for event in events:
            if self.register(
                event
            ):
                added += 1

        return added

    def list_all(
        self,
    ) -> tuple[
        AuthoritativeMarketEventV2,
        ...,
    ]:
        return tuple(
            self._events.values()
        )

    def list_for_market(
        self,
        market_symbol: str,
    ) -> tuple[
        AuthoritativeMarketEventV2,
        ...,
    ]:
        market = get_target_market(
            market_symbol
        ).symbol

        events = [
            event
            for event in self._events.values()
            if market in event.affected_markets
        ]

        return tuple(
            sorted(
                events,
                key=lambda event: (
                    event.scheduled_at
                    or event.published_at
                    or event.observed_at,
                    event.event_id,
                ),
            )
        )

    def unique_for_market(
        self,
        market_symbol: str,
    ) -> tuple[
        AuthoritativeMarketEventV2,
        ...,
    ]:
        events = self.list_for_market(
            market_symbol
        )

        by_group: dict[
            str,
            AuthoritativeMarketEventV2,
        ] = {}

        for event in events:
            current = by_group.get(
                event.event_group_id
            )

            if current is None:
                by_group[
                    event.event_group_id
                ] = event
                continue

            event_time = (
                event.published_at
                or event.effective_at
                or event.scheduled_at
                or event.observed_at
            )

            current_time = (
                current.published_at
                or current.effective_at
                or current.scheduled_at
                or current.observed_at
            )

            if event_time > current_time:
                by_group[
                    event.event_group_id
                ] = event

        return tuple(
            sorted(
                by_group.values(),
                key=lambda event: (
                    event.scheduled_at
                    or event.published_at
                    or event.observed_at,
                    event.event_id,
                ),
            )
        )

    def build_event_risk_payload(
        self,
        *,
        market_symbol: str,
        now: datetime,
        approaching_minutes: int = 60,
        imminent_minutes: int = 10,
        release_window_minutes: int = 5,
        stabilization_minutes: int = 30,
        hard_block_event_types: frozenset[
            str
        ] = frozenset(),
        hard_block_severities: frozenset[
            str
        ] = frozenset(
            {
                "HIGH",
                "CRITICAL",
            }
        ),
    ) -> dict:
        market = get_target_market(
            market_symbol
        ).symbol

        if not _aware(
            now
        ):
            raise ValueError(
                "now must be timezone-aware."
            )

        normalized_block_types = frozenset(
            "_".join(
                value.strip().upper().split()
            )
            for value in hard_block_event_types
        )

        if any(
            value not in EVENT_TYPES
            for value in normalized_block_types
        ):
            raise ValueError(
                "Unknown hard-block event type."
            )

        normalized_severities = frozenset(
            "_".join(
                value.strip().upper().split()
            )
            for value in hard_block_severities
        )

        if any(
            value not in EVENT_SEVERITIES
            for value in normalized_severities
        ):
            raise ValueError(
                "Unknown hard-block severity."
            )

        event_rows = []

        for event in self.unique_for_market(
            market
        ):
            phase = (
                classify_authoritative_event_phase(
                    event,
                    now,
                    approaching_minutes=(
                        approaching_minutes
                    ),
                    imminent_minutes=(
                        imminent_minutes
                    ),
                    release_window_minutes=(
                        release_window_minutes
                    ),
                    stabilization_minutes=(
                        stabilization_minutes
                    ),
                )
            )

            if phase not in EVENT_PHASES:
                raise RuntimeError(
                    "Invalid event phase."
                )

            if phase == "RESOLVED":
                continue

            in_minutes = None

            if event.scheduled_at is not None:
                in_minutes = (
                    event.scheduled_at
                    - now
                ).total_seconds() / 60.0

            policy_block_candidate = (
                event.event_type
                in normalized_block_types
                and event.severity
                in normalized_severities
                and phase
                in BLOCK_CAPABLE_PHASES
            )

            source = (
                get_authoritative_event_source(
                    event.source_id
                )
            )

            event_rows.append(
                {
                    "name": event.title,
                    "event_id": event.event_id,
                    "event_group_id": (
                        event.event_group_id
                    ),
                    "source_id": event.source_id,
                    "source_authoritative": (
                        source.authoritative
                    ),
                    "event_type": (
                        event.event_type
                    ),
                    "severity": event.severity,
                    "phase": phase,
                    "scheduled_at": (
                        event.scheduled_at
                    ),
                    "published_at": (
                        event.published_at
                    ),
                    "effective_at": (
                        event.effective_at
                    ),
                    "in_minutes": (
                        in_minutes
                    ),
                    "policy_block_candidate": (
                        policy_block_candidate
                    ),
                }
            )

        block_entries = any(
            row[
                "policy_block_candidate"
            ]
            for row in event_rows
        )

        return {
            "status": "OK",
            "market": market,
            "source_authoritative": True,
            "threshold_minutes": (
                imminent_minutes
            ),
            "events": event_rows,
            "block_entries": (
                block_entries
            ),
            "policy_event_types": tuple(
                sorted(
                    normalized_block_types
                )
            ),
        }


def new_authoritative_event_registry_v2(
) -> AuthoritativeEventRegistryV2:
    # Import/use catalog here so construction fails early
    # if the static source definitions are invalid.
    assert AUTHORITATIVE_EVENT_SOURCES

    return AuthoritativeEventRegistryV2()

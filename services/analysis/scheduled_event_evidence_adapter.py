"""Strict adapter from provider event records to typed scheduled-market events."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from services.contracts.scheduled_market_event_v1 import (
    ScheduledMarketEventV1,
)


class ScheduledEventEvidenceAdapter:
    """Normalize trusted provider records without calendar inference."""

    def __init__(
        self,
        *,
        source_id: str,
    ) -> None:
        source_id = str(source_id).strip()

        if not source_id:
            raise ValueError("source_id must be non-empty")

        self.source_id = source_id
        self.normalization_count = 0

    @staticmethod
    def _aware(
        value: object,
        name: str,
    ) -> datetime:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                f"{name} must be timezone-aware"
            )

        return value

    @staticmethod
    def _optional_aware(
        value: object,
        name: str,
    ) -> datetime | None:
        if value is None:
            return None

        return ScheduledEventEvidenceAdapter._aware(
            value,
            name,
        )

    @staticmethod
    def _text(
        value: object,
        name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")

        result = " ".join(value.split())

        if not result:
            raise ValueError(f"{name} must be non-empty")

        return result

    @staticmethod
    def _bool(
        value: object,
        name: str,
    ) -> bool:
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be boolean")

        return value

    @staticmethod
    def _messages(
        value: object,
        name: str,
    ) -> tuple[str, ...]:
        if value is None:
            return ()

        if (
            not isinstance(value, Sequence)
            or isinstance(value, (str, bytes, bytearray))
        ):
            raise TypeError(
                f"{name} must be a sequence"
            )

        result = tuple(
            ScheduledEventEvidenceAdapter._text(
                item,
                f"{name} item",
            )
            for item in value
        )

        if len(result) != len(set(result)):
            raise ValueError(
                f"{name} must not contain duplicates"
            )

        return result

    @staticmethod
    def _identities(
        value: object,
    ) -> tuple[tuple[str, str], ...]:
        if value is None:
            return ()

        if (
            not isinstance(value, Sequence)
            or isinstance(value, (str, bytes, bytearray))
        ):
            raise TypeError(
                "affected_market_identities must be a sequence"
            )

        result: list[tuple[str, str]] = []

        for item in value:
            if (
                not isinstance(item, Sequence)
                or isinstance(item, (str, bytes, bytearray))
                or len(item) != 2
            ):
                raise ValueError(
                    "affected market identity must be a pair"
                )

            result.append(
                (
                    str(item[0]).strip().upper(),
                    str(item[1]).strip().upper(),
                )
            )

        return tuple(sorted(result))

    @staticmethod
    def _exchanges(
        value: object,
    ) -> tuple[str, ...]:
        if value is None:
            return ()

        if (
            not isinstance(value, Sequence)
            or isinstance(value, (str, bytes, bytearray))
        ):
            raise TypeError(
                "affected_exchanges must be a sequence"
            )

        result = tuple(
            sorted(
                str(item).strip().upper()
                for item in value
            )
        )

        if any(not item for item in result):
            raise ValueError(
                "affected_exchanges contains an empty value"
            )

        return result

    def normalize(
        self,
        *,
        records: Sequence[Mapping[str, Any]],
        evaluated_at: datetime,
    ) -> tuple[ScheduledMarketEventV1, ...]:
        evaluated_at = self._aware(
            evaluated_at,
            "evaluated_at",
        )

        if (
            not isinstance(records, Sequence)
            or isinstance(records, (str, bytes, bytearray))
        ):
            raise TypeError(
                "records must be a sequence"
            )

        events: list[ScheduledMarketEventV1] = []

        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                raise TypeError(
                    "records must contain mappings"
                )

            data = dict(record)

            source_timestamp = self._aware(
                data.get("source_timestamp"),
                "source_timestamp",
            )

            if source_timestamp > evaluated_at:
                raise ValueError(
                    "source_timestamp cannot follow evaluated_at"
                )

            event = ScheduledMarketEventV1(
                scheduled_market_event_id=self._text(
                    data.get("scheduled_market_event_id"),
                    "scheduled_market_event_id",
                ),
                created_at=evaluated_at,
                event_name=self._text(
                    data.get("event_name"),
                    "event_name",
                ),
                event_category=self._text(
                    data.get("event_category"),
                    "event_category",
                ).upper(),
                scheduled_start=self._aware(
                    data.get("scheduled_start"),
                    "scheduled_start",
                ),
                scheduled_end=self._optional_aware(
                    data.get("scheduled_end"),
                    "scheduled_end",
                ),
                source_id=self.source_id,
                source_timestamp=source_timestamp,
                confirmation_state=self._text(
                    data.get("confirmation_state"),
                    "confirmation_state",
                ).upper(),
                event_status=self._text(
                    data.get("event_status"),
                    "event_status",
                ).upper(),
                severity=self._text(
                    data.get("severity"),
                    "severity",
                ).upper(),
                affected_market_identities=self._identities(
                    data.get("affected_market_identities")
                ),
                affected_exchanges=self._exchanges(
                    data.get("affected_exchanges")
                ),
                analysis_allowed=self._bool(
                    data.get("analysis_allowed"),
                    "analysis_allowed",
                ),
                new_entries_allowed=self._bool(
                    data.get("new_entries_allowed"),
                    "new_entries_allowed",
                ),
                session_override_state=self._text(
                    data.get("session_override_state"),
                    "session_override_state",
                ).upper(),
                blockers=self._messages(
                    data.get("blockers"),
                    "blockers",
                ),
                warnings=self._messages(
                    data.get("warnings"),
                    "warnings",
                ),
                metadata={
                    "adapter": (
                        "ScheduledEventEvidenceAdapter"
                    ),
                    "provider_record_index": index,
                },
            )

            events.append(event)

        identifiers = tuple(
            event.scheduled_market_event_id
            for event in events
        )

        if len(identifiers) != len(set(identifiers)):
            raise ValueError(
                "provider returned duplicate event identifiers"
            )

        self.normalization_count += 1

        return tuple(
            sorted(
                events,
                key=lambda item: (
                    item.scheduled_market_event_id
                ),
            )
        )

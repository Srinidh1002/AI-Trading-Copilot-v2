"""Strict normalization of provider global-market observations."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from services.contracts.external_market_observation_v1 import (
    ExternalMarketObservationV1,
)


class GlobalMarketEvidenceAdapter:
    """Build typed external observations without directional inference."""

    def __init__(self, *, source_id: str) -> None:
        source_id = str(source_id).strip()

        if not source_id:
            raise ValueError("source_id must be non-empty")

        self.source_id = source_id
        self.normalization_count = 0

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
    def _text(value: object, name: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")

        result = " ".join(value.split())

        if not result:
            raise ValueError(f"{name} must be non-empty")

        return result

    @staticmethod
    def _optional_number(
        value: object,
        name: str,
    ) -> float | None:
        if value is None:
            return None

        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise TypeError(f"{name} must be numeric or None")

        return float(value)

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
            raise TypeError(f"{name} must be a sequence")

        result = tuple(
            GlobalMarketEvidenceAdapter._text(
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

        identities: list[tuple[str, str]] = []

        for item in value:
            if (
                not isinstance(item, Sequence)
                or isinstance(item, (str, bytes, bytearray))
                or len(item) != 2
            ):
                raise ValueError(
                    "affected market identity must be a pair"
                )

            identities.append(
                (
                    str(item[0]).strip().upper(),
                    str(item[1]).strip().upper(),
                )
            )

        result = tuple(sorted(identities))

        if len(result) != len(set(result)):
            raise ValueError(
                "affected market identities must be unique"
            )

        return result

    def normalize(
        self,
        *,
        records: Sequence[Mapping[str, Any]],
        evaluated_at: datetime,
    ) -> tuple[ExternalMarketObservationV1, ...]:
        evaluated_at = self._aware(
            evaluated_at,
            "evaluated_at",
        )

        if (
            not isinstance(records, Sequence)
            or isinstance(records, (str, bytes, bytearray))
        ):
            raise TypeError("records must be a sequence")

        observations: list[ExternalMarketObservationV1] = []

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

            observation = ExternalMarketObservationV1(
                external_market_observation_id=self._text(
                    data.get("external_market_observation_id"),
                    "external_market_observation_id",
                ),
                created_at=evaluated_at,
                canonical_name=self._text(
                    data.get("canonical_name"),
                    "canonical_name",
                ).upper(),
                observation_type=self._text(
                    data.get("observation_type"),
                    "observation_type",
                ).upper(),
                market_region=self._text(
                    data.get("market_region"),
                    "market_region",
                ).upper(),
                asset_class=self._text(
                    data.get("asset_class"),
                    "asset_class",
                ).upper(),
                source_id=self.source_id,
                source_timestamp=source_timestamp,
                session_reference=self._text(
                    data.get("session_reference"),
                    "session_reference",
                ).upper(),
                current_value=self._optional_number(
                    data.get("current_value"),
                    "current_value",
                ),
                previous_value=self._optional_number(
                    data.get("previous_value"),
                    "previous_value",
                ),
                change_value=self._optional_number(
                    data.get("change_value"),
                    "change_value",
                ),
                change_percent=self._optional_number(
                    data.get("change_percent"),
                    "change_percent",
                ),
                direction=self._text(
                    data.get("direction"),
                    "direction",
                ).upper(),
                observation_status=self._text(
                    data.get("observation_status"),
                    "observation_status",
                ).upper(),
                is_delayed=data.get("is_delayed", False),
                delay_seconds=data.get("delay_seconds", 0.0),
                affected_market_identities=self._identities(
                    data.get("affected_market_identities")
                ),
                blockers=self._messages(
                    data.get("blockers"),
                    "blockers",
                ),
                warnings=self._messages(
                    data.get("warnings"),
                    "warnings",
                ),
                metadata={
                    "adapter": "GlobalMarketEvidenceAdapter",
                    "provider_record_index": index,
                },
            )

            observations.append(observation)

        canonical_names = tuple(
            item.canonical_name
            for item in observations
        )

        if len(canonical_names) != len(set(canonical_names)):
            raise ValueError(
                "provider returned duplicate canonical observations"
            )

        self.normalization_count += 1

        return tuple(
            sorted(
                observations,
                key=lambda item: item.canonical_name,
            )
        )

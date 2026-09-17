"""Strict normalization of provider institutional-flow records."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from services.contracts.institutional_flow_snapshot_v1 import (
    InstitutionalFlowSnapshotV1,
)


class InstitutionalFlowEvidenceAdapter:
    """Build one typed snapshot without directional inference."""

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
    def _date(value: object, name: str) -> date:
        if isinstance(value, datetime) or not isinstance(value, date):
            raise TypeError(f"{name} must be a date")

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
            InstitutionalFlowEvidenceAdapter._text(
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
        record: Mapping[str, Any],
        evaluated_at: datetime,
    ) -> InstitutionalFlowSnapshotV1:
        evaluated_at = self._aware(
            evaluated_at,
            "evaluated_at",
        )

        if not isinstance(record, Mapping):
            raise TypeError("record must be a mapping")

        data = dict(record)

        source_timestamp = self._aware(
            data.get("source_timestamp"),
            "source_timestamp",
        )

        if source_timestamp > evaluated_at:
            raise ValueError(
                "source_timestamp cannot follow evaluated_at"
            )

        snapshot = InstitutionalFlowSnapshotV1(
            institutional_flow_snapshot_id=self._text(
                data.get("institutional_flow_snapshot_id"),
                "institutional_flow_snapshot_id",
            ),
            created_at=evaluated_at,
            trading_date=self._date(
                data.get("trading_date"),
                "trading_date",
            ),
            source_id=self.source_id,
            source_timestamp=source_timestamp,
            publication_state=self._text(
                data.get("publication_state"),
                "publication_state",
            ).upper(),
            session_reference=self._text(
                data.get("session_reference"),
                "session_reference",
            ).upper(),
            currency=self._text(
                data.get("currency"),
                "currency",
            ).upper(),
            cash_flow_unit=self._text(
                data.get("cash_flow_unit"),
                "cash_flow_unit",
            ).upper(),
            derivatives_position_unit=self._text(
                data.get("derivatives_position_unit"),
                "derivatives_position_unit",
            ).upper(),
            fii_cash_net=self._optional_number(
                data.get("fii_cash_net"),
                "fii_cash_net",
            ),
            dii_cash_net=self._optional_number(
                data.get("dii_cash_net"),
                "dii_cash_net",
            ),
            fii_index_futures_net=self._optional_number(
                data.get("fii_index_futures_net"),
                "fii_index_futures_net",
            ),
            fii_index_options_net=self._optional_number(
                data.get("fii_index_options_net"),
                "fii_index_options_net",
            ),
            flow_status=self._text(
                data.get("flow_status"),
                "flow_status",
            ).upper(),
            is_delayed=bool(data.get("is_delayed", False)),
            delay_seconds=float(
                data.get("delay_seconds", 0.0)
            ),
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
                "adapter": (
                    "InstitutionalFlowEvidenceAdapter"
                ),
            },
        )

        self.normalization_count += 1
        return snapshot

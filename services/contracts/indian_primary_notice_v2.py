"""Normalized Indian primary-source notice contracts.

This contract preserves source-native facts before they are allowed into
the authoritative event registry.

Company/exchange disclosures remain symbol-scoped until a separate
constituent/index resolver establishes market impact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from services.contracts.authoritative_event_v2 import (
    EVENT_SEVERITIES,
    EVENT_TYPES,
)


INDIAN_PRIMARY_SOURCE_IDS = frozenset(
    {
        "RBI",
        "SEBI",
        "NSE",
        "BSE",
        "MCX",
    }
)

PRIMARY_NOTICE_KINDS = frozenset(
    {
        "PRESS_RELEASE",
        "CIRCULAR",
        "CORPORATE_ANNOUNCEMENT",
        "CORPORATE_ACTION",
        "EXCHANGE_NOTICE",
    }
)

MARKET_SCOPE_POLICIES = frozenset(
    {
        "SOURCE_DEFAULT",
        "SYMBOL_RESOLUTION_REQUIRED",
    }
)


def _text(
    value: object,
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    return value or None


def _token(
    value: object,
) -> str:
    text = _text(
        value
    )

    if text is None:
        return ""

    return "_".join(
        text.upper().split()
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


def _https_url(
    value: object,
) -> str:
    text = _text(
        value
    )

    if text is None:
        raise ValueError(
            "source_url is required."
        )

    parsed = urlparse(
        text
    )

    if (
        parsed.scheme.lower()
        != "https"
        or not parsed.hostname
    ):
        raise ValueError(
            "source_url must use HTTPS."
        )

    return text


@dataclass(
    frozen=True,
    slots=True,
)
class IndianPrimaryNoticeV2:
    source_id: str
    notice_kind: str

    title: str
    published_at: datetime
    source_url: str

    source_item_id: str | None = None
    detail_text: str | None = None

    affected_symbols: tuple[
        str,
        ...,
    ] = ()

    source_received_at: (
        datetime
        | None
    ) = None

    source_disseminated_at: (
        datetime
        | None
    ) = None

    schema_version: str = (
        "indian_primary_notice.v2"
    )

    def __post_init__(
        self,
    ) -> None:
        source_id = _token(
            self.source_id
        )

        notice_kind = _token(
            self.notice_kind
        )

        title = _text(
            self.title
        )

        source_item_id = _text(
            self.source_item_id
        )

        detail_text = _text(
            self.detail_text
        )

        if (
            source_id
            not in INDIAN_PRIMARY_SOURCE_IDS
        ):
            raise ValueError(
                "Unsupported Indian primary source."
            )

        if (
            notice_kind
            not in PRIMARY_NOTICE_KINDS
        ):
            raise ValueError(
                "Unsupported primary notice kind."
            )

        if title is None:
            raise ValueError(
                "title is required."
            )

        if not _aware(
            self.published_at
        ):
            raise ValueError(
                "published_at must be timezone-aware."
            )

        source_url = _https_url(
            self.source_url
        )

        if not isinstance(
            self.affected_symbols,
            tuple,
        ):
            raise ValueError(
                "affected_symbols must be a tuple."
            )

        symbols = tuple(
            value
            for value in (
                _text(
                    symbol
                )
                for symbol
                in self.affected_symbols
            )
            if value is not None
        )

        if len(
            symbols
        ) != len(
            self.affected_symbols
        ):
            raise ValueError(
                "Invalid affected symbol."
            )

        symbols = tuple(
            symbol.upper()
            for symbol
            in symbols
        )

        if len(
            set(
                symbols
            )
        ) != len(
            symbols
        ):
            raise ValueError(
                "Duplicate affected symbols."
            )

        for (
            field_name,
            value,
        ) in (
            (
                "source_received_at",
                self.source_received_at,
            ),
            (
                "source_disseminated_at",
                self.source_disseminated_at,
            ),
        ):
            if (
                value is not None
                and not _aware(
                    value
                )
            ):
                raise ValueError(
                    f"{field_name} must be timezone-aware."
                )

        if (
            self.source_received_at
            is not None
            and self.source_disseminated_at
            is not None
            and self.source_disseminated_at
            < self.source_received_at
        ):
            raise ValueError(
                "Dissemination cannot precede source receipt."
            )

        if (
            self.schema_version
            != "indian_primary_notice.v2"
        ):
            raise ValueError(
                "Invalid primary notice schema."
            )

        object.__setattr__(
            self,
            "source_id",
            source_id,
        )

        object.__setattr__(
            self,
            "notice_kind",
            notice_kind,
        )

        object.__setattr__(
            self,
            "title",
            title,
        )

        object.__setattr__(
            self,
            "source_item_id",
            source_item_id,
        )

        object.__setattr__(
            self,
            "detail_text",
            detail_text,
        )

        object.__setattr__(
            self,
            "affected_symbols",
            symbols,
        )

        object.__setattr__(
            self,
            "source_url",
            source_url,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class ClassifiedPrimaryNoticeV2:
    notice: IndianPrimaryNoticeV2

    event_type: str
    severity: str
    market_scope_policy: str
    classification_reason: str

    schema_version: str = (
        "classified_primary_notice.v2"
    )

    def __post_init__(
        self,
    ) -> None:
        event_type = _token(
            self.event_type
        )

        severity = _token(
            self.severity
        )

        scope = _token(
            self.market_scope_policy
        )

        reason = _text(
            self.classification_reason
        )

        if (
            event_type
            not in EVENT_TYPES
        ):
            raise ValueError(
                "Unsupported event type."
            )

        if (
            severity
            not in EVENT_SEVERITIES
        ):
            raise ValueError(
                "Unsupported event severity."
            )

        if (
            scope
            not in MARKET_SCOPE_POLICIES
        ):
            raise ValueError(
                "Unsupported market scope policy."
            )

        if reason is None:
            raise ValueError(
                "classification_reason is required."
            )

        object.__setattr__(
            self,
            "event_type",
            event_type,
        )

        object.__setattr__(
            self,
            "severity",
            severity,
        )

        object.__setattr__(
            self,
            "market_scope_policy",
            scope,
        )

        object.__setattr__(
            self,
            "classification_reason",
            reason,
        )

        if (
            self.schema_version
            != "classified_primary_notice.v2"
        ):
            raise ValueError(
                "Invalid classified notice schema."
            )

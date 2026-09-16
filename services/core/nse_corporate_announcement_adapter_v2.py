"""NSE official equity corporate-announcement adapter.

The endpoint used here was discovered directly from NSE's own production
corporate-filings JavaScript:

    /api/corporate-announcements?index=equities

Live records provide symbol, ISIN, stable sequence id, attachment,
``an_dt`` and ``exchdisstime``.

The timestamp strings currently contain exact local wall-clock values but
no explicit source timezone.  They therefore remain
LOCAL_DATETIME_NO_ZONE candidates and are not promoted directly into
IndianPrimaryNoticeV2.
"""

from __future__ import annotations

from datetime import datetime
import json

from services.contracts.exchange_disclosure_candidate_v2 import (
    ExchangeDisclosureCandidateV2,
)


NSE_CORPORATE_ANNOUNCEMENTS_URL = (
    "https://www.nseindia.com/"
    "api/corporate-announcements"
    "?index=equities"
)


def _text(value: object) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()
    return value or None


def _scalar_text(
    value: object,
) -> str | None:
    if isinstance(
        value,
        bool,
    ):
        return None

    if isinstance(
        value,
        (
            int,
            str,
        ),
    ):
        text = str(
            value
        ).strip()

        return text or None

    return None


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


def _parse_nse_local_time(
    value: str | None,
) -> datetime | None:
    text = _text(
        value
    )

    if text is None:
        return None

    try:
        return datetime.strptime(
            text,
            "%d-%b-%Y %H:%M:%S",
        )

    except ValueError:
        return None


def parse_nse_corporate_announcements_json(
    payload: str,
    *,
    observed_at: datetime,
) -> tuple[
    ExchangeDisclosureCandidateV2,
    ...,
]:
    if not _aware(
        observed_at
    ):
        raise ValueError(
            "observed_at must be timezone-aware."
        )

    if not isinstance(
        payload,
        str,
    ):
        raise ValueError(
            "NSE announcement payload must be text."
        )

    try:
        records = json.loads(
            payload
        )

    except json.JSONDecodeError as exc:
        raise ValueError(
            "NSE announcement payload is not valid JSON."
        ) from exc

    if not isinstance(
        records,
        list,
    ):
        raise ValueError(
            "NSE announcement payload must be a JSON list."
        )

    output = []
    seen = set()

    for row in records:
        if not isinstance(
            row,
            dict,
        ):
            continue

        source_item_id = _scalar_text(
            row.get(
                "seq_id"
            )
        )

        symbol = _text(
            row.get(
                "symbol"
            )
        )

        company_name = _text(
            row.get(
                "sm_name"
            )
        )

        isin = _text(
            row.get(
                "sm_isin"
            )
        )

        description = _text(
            row.get(
                "desc"
            )
        )

        attachment_text = _text(
            row.get(
                "attchmntText"
            )
        )

        attachment_url = _text(
            row.get(
                "attchmntFile"
            )
        )

        raw_primary = _text(
            row.get(
                "an_dt"
            )
        )

        raw_disseminated = _text(
            row.get(
                "exchdisstime"
            )
        )

        primary_local = (
            _parse_nse_local_time(
                raw_primary
            )
        )

        disseminated_local = (
            _parse_nse_local_time(
                raw_disseminated
            )
        )

        if (
            source_item_id is None
            or symbol is None
            or company_name is None
            or raw_primary is None
            or primary_local is None
        ):
            continue

        title = (
            description
            or attachment_text
            or (
                f"{company_name} "
                "corporate announcement"
            )
        )

        detail_text = (
            attachment_text
            if (
                attachment_text
                and attachment_text
                != title
            )
            else None
        )

        if source_item_id in seen:
            continue

        seen.add(
            source_item_id
        )

        output.append(
            ExchangeDisclosureCandidateV2(
                source_id="NSE",
                disclosure_kind=(
                    "CORPORATE_ANNOUNCEMENT"
                ),
                company_name=company_name,
                title=title,
                source_item_id=(
                    source_item_id
                ),
                source_url=(
                    NSE_CORPORATE_ANNOUNCEMENTS_URL
                ),
                observed_at=(
                    observed_at
                ),
                raw_primary_time=(
                    raw_primary
                ),
                primary_time_local=(
                    primary_local
                ),
                primary_time_semantics=(
                    "NSE_AN_DT"
                ),
                exchange_symbol=(
                    symbol
                ),
                security_code=None,
                isin=isin,
                detail_text=(
                    detail_text
                ),
                attachment_url=(
                    attachment_url
                ),
                raw_disseminated_time=(
                    raw_disseminated
                    if (
                        disseminated_local
                        is not None
                    )
                    else None
                ),
                disseminated_time_local=(
                    disseminated_local
                ),
                timestamp_precision=(
                    "LOCAL_DATETIME_NO_ZONE"
                ),
                timezone_status=(
                    "SOURCE_UNSPECIFIED"
                ),
            )
        )

    return tuple(
        output
    )


class NSECorporateAnnouncementAdapterV2:
    def __init__(
        self,
        transport,
    ) -> None:
        if transport is None:
            raise ValueError(
                "transport is required."
            )

        self.transport = (
            transport
        )

    def fetch_candidates(
        self,
        *,
        observed_at: datetime,
    ) -> tuple[
        ExchangeDisclosureCandidateV2,
        ...,
    ]:
        payload = (
            self.transport
            .fetch_text(
                NSE_CORPORATE_ANNOUNCEMENTS_URL,
                accepted_content_types=(
                    "application/json",
                    "text/json",
                    "text/plain",
                ),
            )
        )

        return (
            parse_nse_corporate_announcements_json(
                payload,
                observed_at=(
                    observed_at
                ),
            )
        )

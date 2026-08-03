"""Read INDIA_VIX once per certified parent cycle; this boundary never orders."""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from threading import RLock
from zoneinfo import ZoneInfo

from services.contracts.india_vix_capture_result_v1 import (
    IndiaVixCaptureResultV1,
)
from services.contracts.india_vix_previous_close_policy_v1 import (
    DEFAULT_INDIA_VIX_PREVIOUS_CLOSE_POLICY,
    IndiaVixPreviousClosePolicyV1,
)
from services.contracts.market_data_provenance_v1 import (
    MarketDataProvenanceV1,
)

_IST = ZoneInfo("Asia/Kolkata")
_ANGEL_TIME_FORMAT = "%d-%b-%Y %H:%M:%S"


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        return _aware(value, "provider timestamp")
    if not isinstance(value, str):
        raise ValueError("INDIA_VIX_PROVIDER_TIMESTAMP_UNPROVEN")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _aware(parsed, "provider timestamp")
    except ValueError:
        try:
            return datetime.strptime(
                value,
                _ANGEL_TIME_FORMAT,
            ).replace(tzinfo=_IST)
        except ValueError as exc:
            raise ValueError(
                "INDIA_VIX_PROVIDER_TIMESTAMP_UNPROVEN"
            ) from exc


class IndiaVixLiveReader:
    """Same-process master cache and exactly-once capture per cycle."""

    def __init__(
        self,
        *,
        master_fetcher: Callable[
            [], Sequence[Mapping[str, object]]
        ],
        market_client: object,
        clock: Callable[[], datetime],
        previous_close_policy: IndiaVixPreviousClosePolicyV1 = (
            DEFAULT_INDIA_VIX_PREVIOUS_CLOSE_POLICY
        ),
    ) -> None:
        if type(previous_close_policy) is not IndiaVixPreviousClosePolicyV1:
            raise TypeError(
                "previous_close_policy must be exact "
                "IndiaVixPreviousClosePolicyV1"
            )
        self._master_fetcher = master_fetcher
        self._market_client = market_client
        self._clock = clock
        self._previous_close_policy = previous_close_policy
        self._master: Mapping[str, object] | None = None
        self._captures: dict[str, IndiaVixCaptureResultV1] = {}
        self._lock = RLock()
        self.master_resolution_count = 0
        self.quote_count = 0

    def _now(self) -> datetime:
        return _aware(self._clock(), "clock")

    def _master_record(self) -> Mapping[str, object]:
        if self._master is not None:
            return self._master

        records = self._master_fetcher()
        self.master_resolution_count += 1
        if not isinstance(records, Sequence):
            raise ValueError("INDIA_VIX_MASTER_INVALID")

        matches = [
            record
            for record in records
            if isinstance(record, Mapping)
            and str(record.get("symbol")) == "India VIX"
            and str(record.get("name")) == "INDIA VIX"
            and str(record.get("exch_seg")).upper() == "NSE"
            and str(record.get("instrumenttype")).upper() == "AMXIDX"
        ]
        if len(matches) != 1 or not str(
            matches[0].get("token", "")
        ).strip():
            raise ValueError(
                "INDIA_VIX_MASTER_AMBIGUOUS"
                if len(matches) > 1
                else "INDIA_VIX_MASTER_NOT_FOUND"
            )

        self._master = matches[0]
        return self._master

    def _unavailable(
        self,
        cycle_id: str,
        now: datetime,
        code: str,
    ) -> IndiaVixCaptureResultV1:
        return IndiaVixCaptureResultV1(
            capture_id=f"india-vix:{cycle_id}",
            cycle_id=cycle_id,
            canonical_name="INDIA_VIX",
            provider="ANGEL_SMARTAPI",
            provider_symbol=None,
            provider_exchange=None,
            provider_token=None,
            instrument_type=None,
            current_value=None,
            previous_close=None,
            provider_timestamp=None,
            evaluated_at=now,
            provenance=MarketDataProvenanceV1(
                "ANGEL_SMARTAPI",
                None,
                None,
                "LIVE",
                now,
                now,
                False,
                None,
                None,
            ),
            source_status="UNAVAILABLE",
            blockers=(code,),
            metadata={
                "previous_close_policy_id": (
                    self._previous_close_policy.policy_id
                ),
            },
        )

    def capture(self, cycle_id: str) -> IndiaVixCaptureResultV1:
        if not isinstance(cycle_id, str) or not cycle_id.strip():
            raise ValueError("cycle_id must be non-empty")

        with self._lock:
            cached = self._captures.get(cycle_id)
            if cached is not None:
                return cached

            now = self._now()
            try:
                master = self._master_record()
                token = str(master["token"])

                self.quote_count += 1
                raw = self._market_client.get_market_data(
                    "FULL",
                    {"NSE": [token]},
                )
                received = self._now()

                if not isinstance(raw, Mapping):
                    raise ValueError("INDIA_VIX_QUOTE_INVALID")

                data = raw.get("data")
                fetched = (
                    data.get("fetched", ())
                    if isinstance(data, Mapping)
                    else ()
                )
                row = (
                    fetched[0]
                    if isinstance(fetched, Sequence)
                    and len(fetched) == 1
                    and isinstance(fetched[0], Mapping)
                    else None
                )
                if row is None:
                    raise ValueError("INDIA_VIX_QUOTE_INVALID")

                identity = (
                    str(row.get("exchange", "")).upper(),
                    str(row.get("symbolToken", "")),
                    str(row.get("tradingSymbol", "")),
                )
                if identity != ("NSE", token, "India VIX"):
                    raise ValueError(
                        "INDIA_VIX_QUOTE_IDENTITY_MISMATCH"
                    )

                current = row.get("ltp")
                if (
                    isinstance(current, bool)
                    or type(current) not in (int, float)
                    or not math.isfinite(float(current))
                    or float(current) <= 0.0
                ):
                    raise ValueError("INDIA_VIX_QUOTE_VALUE_INVALID")

                previous, previous_field, previous_blockers = (
                    self._previous_close_policy.resolve(row)
                )
                if previous_blockers:
                    raise ValueError(previous_blockers[0])

                provider_timestamp = _timestamp(
                    row.get("exchFeedTime")
                )
                age = (received - provider_timestamp).total_seconds()

                metadata = {
                    "previous_close_policy_id": (
                        self._previous_close_policy.policy_id
                    ),
                    "previous_close_source_field": previous_field,
                    "previous_close_effective_from": (
                        self._previous_close_policy.effective_from.isoformat()
                    ),
                    "provider_timestamp_field": "exchFeedTime",
                    "quote_age_seconds": age,
                }

                if (
                    age
                    > self._previous_close_policy.maximum_quote_age_seconds
                    or age
                    < -self._previous_close_policy.maximum_future_skew_seconds
                ):
                    result = IndiaVixCaptureResultV1(
                        capture_id=f"india-vix:{cycle_id}",
                        cycle_id=cycle_id,
                        canonical_name="INDIA_VIX",
                        provider="ANGEL_SMARTAPI",
                        provider_symbol="India VIX",
                        provider_exchange="NSE",
                        provider_token=token,
                        instrument_type="AMXIDX",
                        current_value=float(current),
                        previous_close=previous,
                        provider_timestamp=provider_timestamp,
                        evaluated_at=received,
                        provenance=MarketDataProvenanceV1(
                            "ANGEL_SMARTAPI",
                            "India VIX",
                            "NSE",
                            "LIVE",
                            now,
                            received,
                            False,
                            None,
                            None,
                        ),
                        source_status="STALE",
                        blockers=(
                            "INDIA_VIX_PROVIDER_TIMESTAMP_NOT_FRESH",
                        ),
                        metadata=metadata,
                    )
                else:
                    result = IndiaVixCaptureResultV1(
                        capture_id=f"india-vix:{cycle_id}",
                        cycle_id=cycle_id,
                        canonical_name="INDIA_VIX",
                        provider="ANGEL_SMARTAPI",
                        provider_symbol="India VIX",
                        provider_exchange="NSE",
                        provider_token=token,
                        instrument_type="AMXIDX",
                        current_value=float(current),
                        previous_close=previous,
                        provider_timestamp=provider_timestamp,
                        evaluated_at=received,
                        provenance=MarketDataProvenanceV1(
                            "ANGEL_SMARTAPI",
                            "India VIX",
                            "NSE",
                            "LIVE",
                            now,
                            received,
                            False,
                            None,
                            None,
                        ),
                        source_status="READY",
                        metadata=metadata,
                    )
            except ValueError as exc:
                result = self._unavailable(
                    cycle_id,
                    now,
                    str(exc),
                )
            except Exception as exc:
                result = self._unavailable(
                    cycle_id,
                    now,
                    "INDIA_VIX_CAPTURE_FAILED_"
                    f"{type(exc).__name__.upper()}",
                )

            self._captures[cycle_id] = result
            return result

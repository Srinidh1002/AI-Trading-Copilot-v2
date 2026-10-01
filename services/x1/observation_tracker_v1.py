"""Per-instrument observation quality tracker for the X1 data plane.

The tracker is a pure classifier. It performs no I/O, does not touch the
network, and does not mutate the observations it classifies. It keeps a
bounded amount of per-instrument state so that duplicates, out-of-order
observations, and per-instrument silence can be classified independently
of global socket state.

Design constraints (per X1 review corrections B and H):

* Classify each observation independently per canonical instrument.
* Never assume provider timestamps are unique.
* Never use local receipt time as a substitute for a missing provider
  timestamp when deciding whether a repeated observation is new.
* Fail closed: refuse to classify an observation as ``VALID`` if we do
  not have enough information to be sure.
* Distinguish expected market inactivity from unexpected silence by
  accepting an optional session-state resolver. When the resolver is
  absent or returns ``None``, silence is treated as suspected.
* A healthy socket does not make every subscribed instrument healthy:
  the tracker reports silence per instrument, never in aggregate.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from threading import RLock
from typing import Any

from services.x1.observation_identity_v1 import (
    ObservationIdentityError,
    ObservationIdentityV1,
    build_observation_identity_v1,
)


class ObservationQualityV1(StrEnum):
    VALID = "VALID"
    SUSPECTED_DUPLICATE = "SUSPECTED_DUPLICATE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    STALE_GENERATION = "STALE_GENERATION"
    FUTURE_DATED = "FUTURE_DATED"
    STALE_DATED = "STALE_DATED"
    MALFORMED = "MALFORMED"


class InstrumentSilenceStateV1(StrEnum):
    NO_TICK_YET = "NO_TICK_YET"
    ACTIVE = "ACTIVE"
    EXPECTED_INACTIVITY = "EXPECTED_INACTIVITY"
    SUSPECTED_SILENCE = "SUSPECTED_SILENCE"


@dataclass(frozen=True, slots=True)
class SessionStateV1:
    """Minimal session-state contract the tracker depends on.

    Callers adapt any existing repository session authority to this
    shape. Returning ``None`` from the resolver means "unknown"; the
    tracker treats unknown as conservatively not active.
    """

    market_symbol: str
    market_date: date
    is_active: bool
    session_open_at: datetime | None = None
    session_close_at: datetime | None = None


SessionStateResolverV1 = Callable[..., "SessionStateV1 | None"]


@dataclass(frozen=True, slots=True)
class ObservationClassificationV1:
    canonical_instrument_id: str
    quality: ObservationQualityV1
    identity: ObservationIdentityV1 | None
    reason_code: str | None
    observation_index: int
    first_seen_at: datetime

    @property
    def is_valid(self) -> bool:
        return self.quality is ObservationQualityV1.VALID


@dataclass(frozen=True, slots=True)
class InstrumentSilenceV1:
    canonical_instrument_id: str
    state: InstrumentSilenceStateV1
    last_valid_received_at: datetime | None
    last_valid_provider_timestamp: datetime | None
    seconds_since_last_valid: float | None
    expected_active: bool
    reason_code: str | None


@dataclass(slots=True)
class _InstrumentState:
    last_identity_sha256: str | None = None
    last_provider_timestamp: datetime | None = None
    last_receipt_at: datetime | None = None
    accepted_count: int = 0
    duplicate_count: int = 0
    out_of_order_count: int = 0
    stale_generation_count: int = 0
    malformed_count: int = 0
    future_dated_count: int = 0
    stale_dated_count: int = 0


class ObservationTrackerV1:
    """Deterministic, thread-safe observation classifier."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        *,
        clock: Callable[[], datetime],
        stale_after_seconds: float = 30.0,
        future_tolerance_seconds: float = 5.0,
        session_state_resolver: SessionStateResolverV1 | None = None,
        max_instruments: int = 512,
    ) -> None:
        for name, value in (
            ("stale_after_seconds", stale_after_seconds),
            ("future_tolerance_seconds", future_tolerance_seconds),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                raise ValueError(
                    f"{name} must be a non-negative number."
                )
        if (
            not isinstance(max_instruments, int)
            or isinstance(max_instruments, bool)
            or max_instruments < 1
        ):
            raise ValueError("max_instruments must be a positive integer.")

        self._clock = clock
        self._stale_after = float(stale_after_seconds)
        self._future_tolerance = float(future_tolerance_seconds)
        self._session_resolver = session_state_resolver
        self._max_instruments = max_instruments
        self._lock = RLock()
        self._instruments: dict[str, _InstrumentState] = {}
        self._observation_index = 0
        self._stale_generation_total = 0

    def classify(
        self,
        record: Mapping[str, Any],
        *,
        connection_generation: int,
        current_generation: int,
    ) -> ObservationClassificationV1:
        with self._lock:
            self._observation_index += 1
            index = self._observation_index
            now = self._coerce_now()

            if (
                not isinstance(connection_generation, int)
                or isinstance(connection_generation, bool)
                or connection_generation < 0
            ):
                return self._malformed(
                    canonical_id="",
                    reason="invalid_connection_generation",
                    index=index,
                    now=now,
                )

            if connection_generation < current_generation:
                self._stale_generation_total += 1
                return self._stale_generation(
                    record=record,
                    generation=connection_generation,
                    index=index,
                    now=now,
                )

            try:
                identity = build_observation_identity_v1(
                    record,
                    connection_generation=connection_generation,
                )
            except ObservationIdentityError as exc:
                return self._malformed(
                    canonical_id=str(
                        record.get("canonical_instrument_id", "") or ""
                    ),
                    reason=f"identity:{type(exc).__name__}",
                    index=index,
                    now=now,
                )

            canonical_id = identity.canonical_instrument_id
            if not canonical_id:
                return self._malformed(
                    canonical_id="",
                    reason="missing_canonical_instrument_id",
                    index=index,
                    now=now,
                )

            state = self._instruments.get(canonical_id)
            if state is None:
                if len(self._instruments) >= self._max_instruments:
                    return self._malformed(
                        canonical_id=canonical_id,
                        reason="tracker_capacity_exceeded",
                        index=index,
                        now=now,
                    )
                state = _InstrumentState()
                self._instruments[canonical_id] = state

            anchor_ts = datetime.fromisoformat(
                identity.anchor_timestamp_iso
            )
            received_at = self._coerce_aware(record.get("received_at"))
            if received_at is None:
                state.malformed_count += 1
                return self._malformed(
                    canonical_id=canonical_id,
                    reason="invalid_received_at",
                    index=index,
                    now=now,
                )

            if anchor_ts > now + timedelta(
                seconds=self._future_tolerance
            ):
                state.future_dated_count += 1
                return ObservationClassificationV1(
                    canonical_instrument_id=canonical_id,
                    quality=ObservationQualityV1.FUTURE_DATED,
                    identity=identity,
                    reason_code="future_dated_observation",
                    observation_index=index,
                    first_seen_at=received_at,
                )

            identity_sha = identity.identity_sha256
            # Duplicate detection is driven by the full canonical
            # identity, not by timestamp_source. The identity already
            # includes provider, symbol, canonical id, connection
            # generation, timestamp source, anchor timestamp and LTP
            # token. Two observations with equal identity are not
            # new evidence, regardless of whether the anchor came
            # from the provider or from local receipt time.
            if state.last_identity_sha256 == identity_sha:
                state.duplicate_count += 1
                return ObservationClassificationV1(
                    canonical_instrument_id=canonical_id,
                    quality=ObservationQualityV1.SUSPECTED_DUPLICATE,
                    identity=identity,
                    reason_code="provider_identity_repeat",
                    observation_index=index,
                    first_seen_at=received_at,
                )

            if (
                identity.timestamp_source == "PROVIDER"
                and state.last_provider_timestamp is not None
                and anchor_ts < state.last_provider_timestamp
            ):
                state.out_of_order_count += 1
                return ObservationClassificationV1(
                    canonical_instrument_id=canonical_id,
                    quality=ObservationQualityV1.OUT_OF_ORDER,
                    identity=identity,
                    reason_code="provider_timestamp_regression",
                    observation_index=index,
                    first_seen_at=received_at,
                )

            if (
                identity.timestamp_source == "PROVIDER"
                and (now - anchor_ts).total_seconds()
                > self._stale_after
            ):
                state.stale_dated_count += 1
                return ObservationClassificationV1(
                    canonical_instrument_id=canonical_id,
                    quality=ObservationQualityV1.STALE_DATED,
                    identity=identity,
                    reason_code="provider_timestamp_too_old",
                    observation_index=index,
                    first_seen_at=received_at,
                )

            state.last_identity_sha256 = identity_sha
            if identity.timestamp_source == "PROVIDER":
                state.last_provider_timestamp = anchor_ts
            state.last_receipt_at = received_at
            state.accepted_count += 1
            return ObservationClassificationV1(
                canonical_instrument_id=canonical_id,
                quality=ObservationQualityV1.VALID,
                identity=identity,
                reason_code=None,
                observation_index=index,
                first_seen_at=received_at,
            )

    def silence_report(
        self,
        canonical_instrument_id: str,
        *,
        market_symbol: str,
    ) -> InstrumentSilenceV1:
        with self._lock:
            now = self._coerce_now()
            state = self._instruments.get(canonical_instrument_id)
            expected_active = self._expected_active(
                market_symbol=market_symbol, now=now
            )

            if state is None or state.last_receipt_at is None:
                return InstrumentSilenceV1(
                    canonical_instrument_id=canonical_instrument_id,
                    state=InstrumentSilenceStateV1.NO_TICK_YET,
                    last_valid_received_at=None,
                    last_valid_provider_timestamp=None,
                    seconds_since_last_valid=None,
                    expected_active=expected_active,
                    reason_code="no_accepted_observation",
                )

            seconds_since = (
                now - state.last_receipt_at
            ).total_seconds()

            if seconds_since <= self._stale_after:
                silence_state = InstrumentSilenceStateV1.ACTIVE
                reason = None
            elif not expected_active:
                silence_state = (
                    InstrumentSilenceStateV1.EXPECTED_INACTIVITY
                )
                reason = "market_expected_inactive"
            else:
                silence_state = (
                    InstrumentSilenceStateV1.SUSPECTED_SILENCE
                )
                reason = "instrument_silent_while_market_active"

            return InstrumentSilenceV1(
                canonical_instrument_id=canonical_instrument_id,
                state=silence_state,
                last_valid_received_at=state.last_receipt_at,
                last_valid_provider_timestamp=state.last_provider_timestamp,
                seconds_since_last_valid=seconds_since,
                expected_active=expected_active,
                reason_code=reason,
            )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "instrument_count": len(self._instruments),
                "observation_index": self._observation_index,
                "stale_generation_total": self._stale_generation_total,
                "instruments": {
                    cid: {
                        "accepted_count": st.accepted_count,
                        "duplicate_count": st.duplicate_count,
                        "out_of_order_count": st.out_of_order_count,
                        "stale_generation_count": st.stale_generation_count,
                        "malformed_count": st.malformed_count,
                        "future_dated_count": st.future_dated_count,
                        "stale_dated_count": st.stale_dated_count,
                    }
                    for cid, st in self._instruments.items()
                },
            }

    # ---------- internals ----------

    def _coerce_now(self) -> datetime:
        now = self._clock()
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError(
                "tracker clock must return timezone-aware datetimes."
            )
        return now.astimezone(UTC)

    @staticmethod
    def _coerce_aware(value: object) -> datetime | None:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            return None
        return value.astimezone(UTC)

    def _expected_active(
        self, *, market_symbol: str, now: datetime
    ) -> bool:
        """Fail-closed: when the session resolver is absent,
        raises, or returns None, treat the market as active so
        that silence is reported as SUSPECTED_SILENCE rather
        than silently downgraded to EXPECTED_INACTIVITY.
        """
        if self._session_resolver is None:
            return True
        try:
            state = self._session_resolver(
                market_symbol=market_symbol,
                evaluated_at=now,
                market_date=now.date(),
            )
        except Exception:
            return True
        if state is None or not isinstance(state, SessionStateV1):
            return True
        return bool(state.is_active)

    def _malformed(
        self,
        *,
        canonical_id: str,
        reason: str,
        index: int,
        now: datetime,
    ) -> ObservationClassificationV1:
        if canonical_id:
            state = self._instruments.get(canonical_id)
            if state is not None:
                state.malformed_count += 1
        return ObservationClassificationV1(
            canonical_instrument_id=canonical_id,
            quality=ObservationQualityV1.MALFORMED,
            identity=None,
            reason_code=reason,
            observation_index=index,
            first_seen_at=now,
        )

    def _stale_generation(
        self,
        *,
        record: Mapping[str, Any],
        generation: int,
        index: int,
        now: datetime,
    ) -> ObservationClassificationV1:
        canonical_id = str(
            record.get("canonical_instrument_id", "") or ""
        )
        if canonical_id:
            state = self._instruments.get(canonical_id)
            if state is not None:
                state.stale_generation_count += 1
        return ObservationClassificationV1(
            canonical_instrument_id=canonical_id,
            quality=ObservationQualityV1.STALE_GENERATION,
            identity=None,
            reason_code=(
                f"observation_from_generation_{generation}"
            ),
            observation_index=index,
            first_seen_at=now,
        )


__all__ = [
    "InstrumentSilenceStateV1",
    "InstrumentSilenceV1",
    "ObservationClassificationV1",
    "ObservationQualityV1",
    "ObservationTrackerV1",
    "SessionStateResolverV1",
    "SessionStateV1",
]

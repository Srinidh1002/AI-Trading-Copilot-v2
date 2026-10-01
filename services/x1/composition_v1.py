"""Opt-in X1 data-plane composition with controlled subscription rollover.

Data-only. No order, execution, decision, risk, position, broker or
certification authority.

Flow:

    FYERS fake socket
        -> normalized tick with connection_generation
        -> generation + lifecycle + instrument-identity validation
        -> per-instrument quality tracking
        -> MarketQuoteV2
        -> SharedMarketDataHubV2
        -> optional X1 observation journal

Rollover safety (X1-R2):

* A replacement whose cache invalidation fails is reported as
  REPLACED_DEGRADED, not REPLACED. The old instrument's canonical id is
  recorded in a retired set and a pending-invalidation queue. Late
  old-instrument callbacks are refused.
* Pending invalidations are retried on every subsequent tick; success
  removes the entry from the queue.
* Multi-instrument compositions refuse rollover, preventing accidental
  unsubscribe of unrelated instruments.
* Journal append failures are tracked explicitly. When require_journal
  is set, evidence is not eligible for replay-certified downstream use
  while the journal is unhealthy.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from services.broker.fyers_streaming_v2 import (
    FyersStreamingDataProviderV2,
)
from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.x1.instrument_rollover_v2 import (
    InstrumentRolloverStatusV2,
    invalidate_from_rollover_v2,
    resolve_instrument_replacement_v2,
)
from services.x1.journal_health_v1 import (
    JournalHealthTrackerV1,
    JournalHealthV1,
)
from services.x1.observation_journal_v1 import (
    ObservationJournalV1,
    ObservationRecordError,
    build_observation_record_v1,
)
from services.x1.observation_tracker_v1 import (
    ObservationTrackerV1,
)
from services.x1.streaming_hub_bridge_v1 import (
    BridgeResultV1,
    StreamingHubBridgeV1,
)


class X1CompositionError(RuntimeError):
    """Composition configuration or lifecycle failure."""


_EMPTY_COUNTS = {"quotes": 0, "depth": 0, "candle_series": 0}

STATUS_NOT_STARTED = "NOT_STARTED"
STATUS_NOT_EXPIRED = "NOT_EXPIRED"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_AMBIGUOUS = "AMBIGUOUS"
STATUS_INVALID_INPUT = "INVALID_INPUT"
STATUS_ROLLBACK = "ROLLBACK"
STATUS_REPLACED = "REPLACED"
STATUS_REPLACED_DEGRADED = "REPLACED_DEGRADED"
STATUS_MULTI_INSTRUMENT = "MULTI_INSTRUMENT_UNSUPPORTED"
STATUS_PENDING_QUEUE_FULL = "PENDING_QUEUE_FULL"

DEFAULT_MAX_RESULT_HISTORY = 4096
DEFAULT_MAX_ROLLOVER_HISTORY = 64
DEFAULT_MAX_PENDING_INVALIDATIONS = 64


@dataclass(frozen=True, slots=True)
class RolloverOutcomeV1:
    status: str
    previous_resolution_id: str
    new_resolution_id: str | None
    hub_invalidation_counts: dict[str, int]
    error_code: str | None
    pending_invalidation: bool = False


@dataclass(slots=True)
class _PendingInvalidation:
    provider: str
    market_symbol: str
    exchange: str
    instrument_type: str
    canonical_instrument_id: str
    previous_resolution_id: str
    previous_provider_symbol: str


class X1DataPlaneCompositionV1:
    """Data-only streaming-to-hub composition."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        *,
        hub: SharedMarketDataHubV2,
        tracker: ObservationTrackerV1,
        streaming: FyersStreamingDataProviderV2,
        consumer_id: str,
        journal: ObservationJournalV1 | None = None,
        require_journal: bool = False,
        max_result_history: int = DEFAULT_MAX_RESULT_HISTORY,
        max_rollover_history: int = DEFAULT_MAX_ROLLOVER_HISTORY,
        max_pending_invalidations: int = DEFAULT_MAX_PENDING_INVALIDATIONS,
    ) -> None:
        if not isinstance(hub, SharedMarketDataHubV2):
            raise X1CompositionError(
                "hub must be SharedMarketDataHubV2."
            )
        if not isinstance(tracker, ObservationTrackerV1):
            raise X1CompositionError(
                "tracker must be ObservationTrackerV1."
            )
        if not isinstance(streaming, FyersStreamingDataProviderV2):
            raise X1CompositionError(
                "streaming must be FyersStreamingDataProviderV2."
            )
        if (
            not isinstance(consumer_id, str)
            or not consumer_id.strip()
        ):
            raise X1CompositionError("consumer_id is required.")
        if journal is not None and not isinstance(
            journal, ObservationJournalV1
        ):
            raise X1CompositionError(
                "journal must be ObservationJournalV1 or None."
            )
        if require_journal and journal is None:
            raise X1CompositionError(
                "require_journal=True requires a journal."
            )
        for name, value in (
            ("max_result_history", max_result_history),
            ("max_rollover_history", max_rollover_history),
            ("max_pending_invalidations", max_pending_invalidations),
        ):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
            ):
                raise X1CompositionError(
                    f"{name} must be a positive integer."
                )

        self._hub = hub
        self._tracker = tracker
        self._streaming = streaming
        self._consumer_id = consumer_id.strip()
        self._bridge = StreamingHubBridgeV1(hub=hub, tracker=tracker)
        self._subscription_id: str | None = None
        self._results: list[BridgeResultV1] = []
        self._journal = journal
        self._require_journal = bool(require_journal)
        self._receipt_counter = 0
        self._current_instrument: Mapping[str, Any] | None = None
        self._rollover_history: list[RolloverOutcomeV1] = []
        self._retired_canonical_ids: set[str] = set()
        self._pending_invalidations: dict[str, _PendingInvalidation] = {}
        self._max_result_history = int(max_result_history)
        self._max_rollover_history = int(max_rollover_history)
        self._max_pending_invalidations = int(max_pending_invalidations)
        self._journal_health = JournalHealthTrackerV1(
            configured=journal is not None,
            required=self._require_journal,
        )

    # ---------- accessors ----------

    @property
    def hub(self) -> SharedMarketDataHubV2:
        return self._hub

    @property
    def tracker(self) -> ObservationTrackerV1:
        return self._tracker

    @property
    def bridge(self) -> StreamingHubBridgeV1:
        return self._bridge

    @property
    def streaming(self) -> FyersStreamingDataProviderV2:
        return self._streaming

    @property
    def consumer_id(self) -> str:
        return self._consumer_id

    @property
    def subscription_id(self) -> str | None:
        return self._subscription_id

    @property
    def journal(self) -> ObservationJournalV1 | None:
        return self._journal

    @property
    def require_journal(self) -> bool:
        return self._require_journal

    @property
    def current_instrument(self) -> Mapping[str, Any] | None:
        return self._current_instrument

    def results(self) -> tuple[BridgeResultV1, ...]:
        return tuple(self._results)

    def rollover_history(self) -> tuple[RolloverOutcomeV1, ...]:
        return tuple(self._rollover_history)

    def retired_canonical_ids(self) -> frozenset[str]:
        return frozenset(self._retired_canonical_ids)

    def pending_invalidation_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._pending_invalidations))

    def journal_health(self) -> JournalHealthV1:
        return self._journal_health.snapshot()

    # ---------- lifecycle ----------

    def start(
        self,
        instruments: Sequence[Mapping[str, Any]],
    ) -> str:
        if self._subscription_id is not None:
            raise X1CompositionError(
                "X1_COMPOSITION_ALREADY_STARTED"
            )
        instruments_tuple = tuple(instruments)
        subscription_id = self._streaming.subscribe(
            instruments_tuple,
            self._on_tick,
        )
        self._subscription_id = subscription_id
        if (
            len(instruments_tuple) == 1
            and isinstance(instruments_tuple[0], Mapping)
        ):
            self._current_instrument = dict(instruments_tuple[0])
        return subscription_id

    def stop(self) -> None:
        if self._subscription_id is None:
            return
        subscription_id = self._subscription_id
        self._subscription_id = None
        self._streaming.unsubscribe(subscription_id)

    # ---------- rollover ----------

    def rollover(
        self,
        *,
        previous_instrument: Mapping[str, Any],
        resolver: Any,
        as_of: datetime,
    ) -> RolloverOutcomeV1:
        if self._subscription_id is None:
            return self._record_outcome(RolloverOutcomeV1(
                status=STATUS_NOT_STARTED,
                previous_resolution_id=_safe_resolution_id(
                    previous_instrument
                ),
                new_resolution_id=None,
                hub_invalidation_counts=dict(_EMPTY_COUNTS),
                error_code="composition_not_started",
            ))

        if self._current_instrument is None:
            return self._record_outcome(RolloverOutcomeV1(
                status=STATUS_MULTI_INSTRUMENT,
                previous_resolution_id=_safe_resolution_id(
                    previous_instrument
                ),
                new_resolution_id=None,
                hub_invalidation_counts=dict(_EMPTY_COUNTS),
                error_code="multi_instrument_rollover_unsupported",
            ))

        if (
            len(self._pending_invalidations)
            >= self._max_pending_invalidations
        ):
            return self._record_outcome(RolloverOutcomeV1(
                status=STATUS_PENDING_QUEUE_FULL,
                previous_resolution_id=_safe_resolution_id(
                    previous_instrument
                ),
                new_resolution_id=None,
                hub_invalidation_counts=dict(_EMPTY_COUNTS),
                error_code="pending_invalidation_queue_full",
            ))

        try:
            resolution = resolve_instrument_replacement_v2(
                resolver=resolver,
                previous_instrument=previous_instrument,
                as_of=as_of,
            )
        except Exception as exc:  # noqa: BLE001 - fail closed
            return self._record_outcome(RolloverOutcomeV1(
                status=STATUS_INVALID_INPUT,
                previous_resolution_id="",
                new_resolution_id=None,
                hub_invalidation_counts=dict(_EMPTY_COUNTS),
                error_code=f"rollover_resolve:{type(exc).__name__}",
            ))

        if resolution.status is InstrumentRolloverStatusV2.NOT_EXPIRED:
            return self._record_outcome(RolloverOutcomeV1(
                status=STATUS_NOT_EXPIRED,
                previous_resolution_id=resolution.previous_resolution_id,
                new_resolution_id=None,
                hub_invalidation_counts=dict(_EMPTY_COUNTS),
                error_code=None,
            ))

        if resolution.status is not InstrumentRolloverStatusV2.REPLACED:
            return self._record_outcome(RolloverOutcomeV1(
                status=resolution.status.value,
                previous_resolution_id=resolution.previous_resolution_id,
                new_resolution_id=None,
                hub_invalidation_counts=dict(_EMPTY_COUNTS),
                error_code=resolution.reason_code,
            ))

        new_instrument = resolution.new_instrument
        if not isinstance(new_instrument, Mapping):
            return self._record_outcome(RolloverOutcomeV1(
                status=STATUS_UNAVAILABLE,
                previous_resolution_id=resolution.previous_resolution_id,
                new_resolution_id=None,
                hub_invalidation_counts=dict(_EMPTY_COUNTS),
                error_code="replacement_not_mapping",
            ))

        old_subscription_id = self._subscription_id

        try:
            new_subscription_id = self._streaming.subscribe(
                (new_instrument,),
                self._on_tick,
            )
        except Exception as exc:  # noqa: BLE001 - fail closed
            return self._record_outcome(RolloverOutcomeV1(
                status=STATUS_UNAVAILABLE,
                previous_resolution_id=resolution.previous_resolution_id,
                new_resolution_id=None,
                hub_invalidation_counts=dict(_EMPTY_COUNTS),
                error_code=f"subscribe_new:{type(exc).__name__}",
            ))

        try:
            self._streaming.unsubscribe(old_subscription_id)
        except Exception as exc:  # noqa: BLE001 - attempt rollback
            rollback_error: str | None = None
            try:
                self._streaming.unsubscribe(new_subscription_id)
            except Exception as rbexc:  # noqa: BLE001 - bounded
                rollback_error = type(rbexc).__name__
            return self._record_outcome(RolloverOutcomeV1(
                status=STATUS_ROLLBACK,
                previous_resolution_id=resolution.previous_resolution_id,
                new_resolution_id=None,
                hub_invalidation_counts=dict(_EMPTY_COUNTS),
                error_code=(
                    f"unsubscribe_old:{type(exc).__name__}"
                    f";rollback:{rollback_error or 'ok'}"
                ),
            ))

        # Physical subscription swap succeeded. From this point on, any
        # in-flight old-instrument callback must be refused. Update
        # composition state before attempting cache invalidation.
        self._subscription_id = new_subscription_id
        old_canonical = previous_instrument.get(
            "canonical_instrument_id"
        )
        if isinstance(old_canonical, str) and old_canonical:
            self._retired_canonical_ids.add(old_canonical)
        self._current_instrument = dict(new_instrument)

        try:
            counts = invalidate_from_rollover_v2(
                hub=self._hub,
                previous_instrument=previous_instrument,
                rollover=resolution,
            )
        except Exception as exc:  # noqa: BLE001 - degrade
            if isinstance(old_canonical, str) and old_canonical:
                pending = _build_pending_invalidation(
                    previous_instrument=previous_instrument,
                    resolution=resolution,
                )
                if pending is not None:
                    self._pending_invalidations[
                        pending.canonical_instrument_id
                    ] = pending
            return self._record_outcome(RolloverOutcomeV1(
                status=STATUS_REPLACED_DEGRADED,
                previous_resolution_id=resolution.previous_resolution_id,
                new_resolution_id=new_instrument.get("resolution_id"),
                hub_invalidation_counts=dict(_EMPTY_COUNTS),
                error_code=f"invalidate:{type(exc).__name__}",
                pending_invalidation=True,
            ))

        return self._record_outcome(RolloverOutcomeV1(
            status=STATUS_REPLACED,
            previous_resolution_id=resolution.previous_resolution_id,
            new_resolution_id=new_instrument.get("resolution_id"),
            hub_invalidation_counts=counts,
            error_code=None,
        ))

    # ---------- internals ----------

    def _record_outcome(
        self, outcome: RolloverOutcomeV1
    ) -> RolloverOutcomeV1:
        self._rollover_history.append(outcome)
        if len(self._rollover_history) > self._max_rollover_history:
            self._rollover_history = self._rollover_history[
                -self._max_rollover_history:
            ]
        return outcome

    def _safe_wall(self) -> datetime:
        return datetime.now(UTC)

    def _retry_pending_invalidations(self) -> None:
        if not self._pending_invalidations:
            return
        for canonical_id, pending in list(
            self._pending_invalidations.items()
        ):
            try:
                self._hub.invalidate_instrument(
                    provider=pending.provider,
                    market_symbol=pending.market_symbol,
                    exchange=pending.exchange,
                    instrument_type=pending.instrument_type,
                    canonical_instrument_id=(
                        pending.canonical_instrument_id
                    ),
                )
            except Exception:  # noqa: BLE001 - retry later
                continue
            self._pending_invalidations.pop(canonical_id, None)

    def _on_tick(self, record: Mapping[str, Any]) -> None:
        # Retry pending invalidations on any incoming activity.
        self._retry_pending_invalidations()

        # Late old-instrument callback protection.
        canonical = record.get("canonical_instrument_id", "")
        if (
            isinstance(canonical, str)
            and canonical
            and canonical in self._retired_canonical_ids
        ):
            return

        # Defense-in-depth: refuse ticks that do not match the tracked
        # single current instrument (multi-instrument compositions have
        # _current_instrument = None and are unaffected).
        current = self._current_instrument
        if current is not None:
            current_canonical = current.get("canonical_instrument_id")
            if (
                isinstance(current_canonical, str)
                and current_canonical
                and canonical != current_canonical
            ):
                return

        try:
            current_generation = int(
                self._streaming.snapshot()["connection_generation"]
            )
        except Exception:  # noqa: BLE001 - callback must not raise
            return

        raw_generation = record.get("connection_generation", -1)
        try:
            record_generation = int(raw_generation)
        except Exception:  # noqa: BLE001 - callback must not raise
            record_generation = -1

        self._receipt_counter += 1
        receipt_index = self._receipt_counter

        try:
            result = self._bridge.handle_observation(
                record,
                connection_generation=record_generation,
                current_generation=current_generation,
            )
        except Exception:  # noqa: BLE001 - callback must not raise
            return

        self._results.append(result)
        if len(self._results) > self._max_result_history:
            self._results = self._results[-self._max_result_history:]

        if self._journal is None:
            return

        try:
            journal_record = build_observation_record_v1(
                record=record,
                classification=result.classification,
                receipt_order_index=receipt_index,
                session_id=self._journal.session_id,
            )
        except ObservationRecordError as exc:
            self._journal_health.record_failure(
                observation_id="",
                reason=f"build:{type(exc).__name__}",
                at=self._safe_wall(),
            )
            return
        except Exception as exc:  # noqa: BLE001 - callback must not raise
            self._journal_health.record_failure(
                observation_id="",
                reason=f"build:{type(exc).__name__}",
                at=self._safe_wall(),
            )
            return

        try:
            self._journal.append(journal_record)
        except Exception as exc:  # noqa: BLE001 - callback must not raise
            self._journal_health.record_failure(
                observation_id=journal_record.observation_id,
                reason=f"append:{type(exc).__name__}",
                at=self._safe_wall(),
            )
            return

        self._journal_health.record_success()


def _safe_resolution_id(previous_instrument: object) -> str:
    if not isinstance(previous_instrument, Mapping):
        return ""
    value = previous_instrument.get("resolution_id")
    return value if isinstance(value, str) else ""


def _build_pending_invalidation(
    *,
    previous_instrument: Mapping[str, Any],
    resolution: Any,
) -> _PendingInvalidation | None:
    provider = previous_instrument.get("provider")
    market_symbol = previous_instrument.get("market_symbol")
    kind = previous_instrument.get("instrument_type")
    canonical_id = previous_instrument.get("canonical_instrument_id")
    if kind == "UNDERLYING":
        exchange = previous_instrument.get("underlying_exchange")
    else:
        exchange = previous_instrument.get("derivative_exchange")
    provider_symbol = previous_instrument.get("provider_symbol")
    if not all(
        isinstance(v, str) and v.strip()
        for v in (provider, market_symbol, kind, canonical_id, exchange)
    ):
        return None
    return _PendingInvalidation(
        provider=provider,
        market_symbol=market_symbol,
        exchange=exchange,
        instrument_type=kind,
        canonical_instrument_id=canonical_id,
        previous_resolution_id=(
            resolution.previous_resolution_id
            if hasattr(resolution, "previous_resolution_id")
            else ""
        ),
        previous_provider_symbol=(
            provider_symbol if isinstance(provider_symbol, str) else ""
        ),
    )


__all__ = [
    "DEFAULT_MAX_PENDING_INVALIDATIONS",
    "DEFAULT_MAX_RESULT_HISTORY",
    "DEFAULT_MAX_ROLLOVER_HISTORY",
    "RolloverOutcomeV1",
    "STATUS_AMBIGUOUS",
    "STATUS_INVALID_INPUT",
    "STATUS_MULTI_INSTRUMENT",
    "STATUS_NOT_EXPIRED",
    "STATUS_NOT_STARTED",
    "STATUS_PENDING_QUEUE_FULL",
    "STATUS_REPLACED",
    "STATUS_REPLACED_DEGRADED",
    "STATUS_ROLLBACK",
    "STATUS_UNAVAILABLE",
    "X1CompositionError",
    "X1DataPlaneCompositionV1",
]

"""Opt-in X1 data-plane composition with controlled subscription rollover.

Wires one streaming adapter to one hub through one bridge. The
composition is:

* **explicit** — it is constructed by the caller only, never by an
  import side effect;
* **opt-in** — it does not install itself into any trading runner, PAPER
  process, scheduled task, or existing provider runtime bundle;
* **data-only** — it has no order, execution, decision, risk, position,
  broker, or certification capability.

Flow implemented here:

    FYERS fake socket
        -> normalized tick
        -> generation validation (tracker)
        -> per-instrument quality tracking (tracker)
        -> MarketQuoteV2 (bridge)
        -> SharedMarketDataHubV2 (bridge)
        -> X1 observation journal (optional, per-observation)

Controlled subscription rollover:

``rollover(previous_instrument, resolver, as_of)`` asks the resolver for
a replacement of a previous instrument. On ``REPLACED`` the composition
subscribes the new instrument first, unsubscribes the old one, then
invalidates the old instrument's cached data. If the old unsubscribe
fails it attempts to roll back by unsubscribing the new subscription.
It never mutates a PAPER position, never auto-rolls an open contract,
and never touches frozen Brain V1 contracts.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True, slots=True)
class RolloverOutcomeV1:
    """Structured outcome of a composition rollover attempt."""

    status: str
    previous_resolution_id: str
    new_resolution_id: str | None
    hub_invalidation_counts: dict[str, int]
    error_code: str | None


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

        self._hub = hub
        self._tracker = tracker
        self._streaming = streaming
        self._consumer_id = consumer_id.strip()
        self._bridge = StreamingHubBridgeV1(
            hub=hub,
            tracker=tracker,
        )
        self._subscription_id: str | None = None
        self._results: list[BridgeResultV1] = []
        self._journal = journal
        self._receipt_counter = 0
        self._current_instrument: Mapping[str, Any] | None = None
        self._rollover_history: list[RolloverOutcomeV1] = []

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
    def current_instrument(self) -> Mapping[str, Any] | None:
        return self._current_instrument

    def results(self) -> tuple[BridgeResultV1, ...]:
        return tuple(self._results)

    def rollover_history(self) -> tuple[RolloverOutcomeV1, ...]:
        return tuple(self._rollover_history)

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

    def rollover(
        self,
        *,
        previous_instrument: Mapping[str, Any],
        resolver: Any,
        as_of: datetime,
    ) -> RolloverOutcomeV1:
        """Replace an expired data subscription with a validated one."""
        if self._subscription_id is None:
            return self._record_outcome(
                RolloverOutcomeV1(
                    status="NOT_STARTED",
                    previous_resolution_id=(
                        previous_instrument.get("resolution_id", "")
                        if isinstance(previous_instrument, Mapping)
                        else ""
                    ),
                    new_resolution_id=None,
                    hub_invalidation_counts=dict(_EMPTY_COUNTS),
                    error_code="composition_not_started",
                )
            )

        try:
            resolution = resolve_instrument_replacement_v2(
                resolver=resolver,
                previous_instrument=previous_instrument,
                as_of=as_of,
            )
        except Exception as exc:  # noqa: BLE001 - fail closed
            return self._record_outcome(
                RolloverOutcomeV1(
                    status="INVALID_INPUT",
                    previous_resolution_id="",
                    new_resolution_id=None,
                    hub_invalidation_counts=dict(_EMPTY_COUNTS),
                    error_code=(
                        f"rollover_resolve:{type(exc).__name__}"
                    ),
                )
            )

        if resolution.status is InstrumentRolloverStatusV2.NOT_EXPIRED:
            return self._record_outcome(
                RolloverOutcomeV1(
                    status="NOT_EXPIRED",
                    previous_resolution_id=(
                        resolution.previous_resolution_id
                    ),
                    new_resolution_id=None,
                    hub_invalidation_counts=dict(_EMPTY_COUNTS),
                    error_code=None,
                )
            )

        if (
            resolution.status
            is not InstrumentRolloverStatusV2.REPLACED
        ):
            return self._record_outcome(
                RolloverOutcomeV1(
                    status=resolution.status.value,
                    previous_resolution_id=(
                        resolution.previous_resolution_id
                    ),
                    new_resolution_id=None,
                    hub_invalidation_counts=dict(_EMPTY_COUNTS),
                    error_code=resolution.reason_code,
                )
            )

        new_instrument = resolution.new_instrument
        if not isinstance(new_instrument, Mapping):
            return self._record_outcome(
                RolloverOutcomeV1(
                    status="UNAVAILABLE",
                    previous_resolution_id=(
                        resolution.previous_resolution_id
                    ),
                    new_resolution_id=None,
                    hub_invalidation_counts=dict(_EMPTY_COUNTS),
                    error_code="replacement_not_mapping",
                )
            )

        old_subscription_id = self._subscription_id

        try:
            new_subscription_id = self._streaming.subscribe(
                (new_instrument,),
                self._on_tick,
            )
        except Exception as exc:  # noqa: BLE001 - fail closed
            return self._record_outcome(
                RolloverOutcomeV1(
                    status="UNAVAILABLE",
                    previous_resolution_id=(
                        resolution.previous_resolution_id
                    ),
                    new_resolution_id=None,
                    hub_invalidation_counts=dict(_EMPTY_COUNTS),
                    error_code=(
                        f"subscribe_new:{type(exc).__name__}"
                    ),
                )
            )

        try:
            self._streaming.unsubscribe(old_subscription_id)
        except Exception as exc:  # noqa: BLE001 - attempt rollback
            rollback_error: str | None = None
            try:
                self._streaming.unsubscribe(new_subscription_id)
            except Exception as rbexc:  # noqa: BLE001 - bounded
                rollback_error = type(rbexc).__name__
            return self._record_outcome(
                RolloverOutcomeV1(
                    status="ROLLBACK",
                    previous_resolution_id=(
                        resolution.previous_resolution_id
                    ),
                    new_resolution_id=None,
                    hub_invalidation_counts=dict(_EMPTY_COUNTS),
                    error_code=(
                        f"unsubscribe_old:{type(exc).__name__}"
                        f";rollback:{rollback_error or 'ok'}"
                    ),
                )
            )

        try:
            counts = invalidate_from_rollover_v2(
                hub=self._hub,
                previous_instrument=previous_instrument,
                rollover=resolution,
            )
        except Exception as exc:  # noqa: BLE001 - bounded diagnostic
            counts = dict(_EMPTY_COUNTS)
            error_code = f"invalidate:{type(exc).__name__}"
        else:
            error_code = None

        self._subscription_id = new_subscription_id
        self._current_instrument = dict(new_instrument)

        return self._record_outcome(
            RolloverOutcomeV1(
                status="REPLACED",
                previous_resolution_id=(
                    resolution.previous_resolution_id
                ),
                new_resolution_id=new_instrument.get(
                    "resolution_id"
                ),
                hub_invalidation_counts=counts,
                error_code=error_code,
            )
        )

    def _record_outcome(
        self, outcome: RolloverOutcomeV1
    ) -> RolloverOutcomeV1:
        self._rollover_history.append(outcome)
        return outcome

    def _on_tick(
        self,
        record: Mapping[str, Any],
    ) -> None:
        try:
            current_generation = int(
                self._streaming.snapshot()[
                    "connection_generation"
                ]
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

        if self._journal is None:
            return
        try:
            journal_record = build_observation_record_v1(
                record=record,
                classification=result.classification,
                receipt_order_index=receipt_index,
                session_id=self._journal.session_id,
            )
        except ObservationRecordError:
            return
        except Exception:  # noqa: BLE001 - callback must not raise
            return
        try:
            self._journal.append(journal_record)
        except Exception:  # noqa: BLE001 - callback must not raise
            return


__all__ = [
    "RolloverOutcomeV1",
    "X1CompositionError",
    "X1DataPlaneCompositionV1",
]

"""X1 streaming-to-hub bridge.

Single-responsibility adapter that:

1. routes a normalized streaming observation through the X1 per-instrument
   observation tracker;
2. refuses to publish anything that is not classified ``VALID``;
3. on ``VALID`` only, builds a provider-neutral ``MarketQuoteV2`` and
   publishes it into ``SharedMarketDataHubV2``.

The bridge is data-only. It has no order, execution, decision, risk,
position, broker, or certification capability. It does not perform network
I/O. It never raises; every failure is returned as a ``BridgeResultV1``
with an explicit classification and reason code.

Design constraints (per X1 review corrections B, C, E, H):

* Duplicate suppression and ordering enforcement are delegated to
  ``ObservationTrackerV1``. The bridge does not re-implement them.
* The bridge never manufactures a quote from insufficient evidence. If
  the fields required to construct a ``MarketQuoteV2`` are missing or
  inconsistent, the bridge returns a MALFORMED result and does not
  publish.
* The bridge does not silently substitute cached or historical values.
  Every published quote carries ``source_type="LIVE"`` and
  ``is_cached=False``.
* Rejected observations are never retained as valid market evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.contracts.market_data_v2 import (
    MarketDataProvenanceV2,
    MarketQuoteV2,
)
from services.core.five_market_universe_v2 import get_target_market
from services.x1.observation_tracker_v1 import (
    ObservationClassificationV1,
    ObservationQualityV1,
    ObservationTrackerV1,
)


class StreamingHubBridgeError(RuntimeError):
    """Bridge configuration failure (raised only from the constructor)."""


@dataclass(frozen=True, slots=True)
class BridgeResultV1:
    """Outcome of one bridge invocation."""

    accepted: bool
    quality: ObservationQualityV1
    reason_code: str | None
    quote_id: str | None
    canonical_instrument_id: str
    classification: ObservationClassificationV1


def _exchange_for(
    market_symbol: str,
    instrument_type: str,
) -> str:
    market = get_target_market(market_symbol)
    if instrument_type == "UNDERLYING":
        return market.underlying_exchange
    return market.derivative_exchange


class StreamingHubBridgeV1:
    """Validate-then-publish bridge with explicit failure classification."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        *,
        hub: SharedMarketDataHubV2,
        tracker: ObservationTrackerV1,
    ) -> None:
        if not isinstance(hub, SharedMarketDataHubV2):
            raise StreamingHubBridgeError(
                "hub must be SharedMarketDataHubV2."
            )
        if not isinstance(tracker, ObservationTrackerV1):
            raise StreamingHubBridgeError(
                "tracker must be ObservationTrackerV1."
            )
        self._hub = hub
        self._tracker = tracker

    @property
    def hub(self) -> SharedMarketDataHubV2:
        return self._hub

    @property
    def tracker(self) -> ObservationTrackerV1:
        return self._tracker

    def handle_observation(
        self,
        record: Mapping[str, Any],
        *,
        connection_generation: int,
        current_generation: int,
    ) -> BridgeResultV1:
        """Classify then, only if VALID, publish. Never raises."""
        try:
            classification = self._tracker.classify(
                record,
                connection_generation=connection_generation,
                current_generation=current_generation,
            )
        except Exception as exc:  # noqa: BLE001 - bounded, classified below
            return BridgeResultV1(
                accepted=False,
                quality=ObservationQualityV1.MALFORMED,
                reason_code=f"tracker:{type(exc).__name__}",
                quote_id=None,
                canonical_instrument_id="",
                classification=ObservationClassificationV1(
                    canonical_instrument_id="",
                    quality=ObservationQualityV1.MALFORMED,
                    identity=None,
                    reason_code=f"tracker:{type(exc).__name__}",
                    observation_index=0,
                    first_seen_at=datetime.now(UTC),
                ),
            )

        if not classification.is_valid:
            return BridgeResultV1(
                accepted=False,
                quality=classification.quality,
                reason_code=classification.reason_code,
                quote_id=None,
                canonical_instrument_id=(
                    classification.canonical_instrument_id
                ),
                classification=classification,
            )

        try:
            quote = self._build_quote(record, classification)
        except Exception as exc:  # noqa: BLE001 - bounded, classified below
            return BridgeResultV1(
                accepted=False,
                quality=ObservationQualityV1.MALFORMED,
                reason_code=f"quote_build:{type(exc).__name__}",
                quote_id=None,
                canonical_instrument_id=(
                    classification.canonical_instrument_id
                ),
                classification=classification,
            )

        try:
            self._hub.publish_quote(quote)
        except Exception as exc:  # noqa: BLE001 - bounded, classified below
            return BridgeResultV1(
                accepted=False,
                quality=ObservationQualityV1.MALFORMED,
                reason_code=f"hub_publish:{type(exc).__name__}",
                quote_id=None,
                canonical_instrument_id=(
                    classification.canonical_instrument_id
                ),
                classification=classification,
            )

        return BridgeResultV1(
            accepted=True,
            quality=ObservationQualityV1.VALID,
            reason_code=None,
            quote_id=quote.quote_id,
            canonical_instrument_id=(
                classification.canonical_instrument_id
            ),
            classification=classification,
        )

    # ---------- internals ----------

    def _build_quote(
        self,
        record: Mapping[str, Any],
        classification: ObservationClassificationV1,
    ) -> MarketQuoteV2:
        if classification.identity is None:
            raise ValueError("classification is missing identity.")

        provider = record["provider"]
        provider_symbol = record["provider_symbol"]
        market_symbol = record["market_symbol"]
        instrument_type = record["instrument_type"]
        canonical_id = record["canonical_instrument_id"]
        observed_at = record["ts"]
        received_at = record["received_at"]
        ltp = float(record["ltp"])

        exchange = _exchange_for(market_symbol, instrument_type)

        provenance = MarketDataProvenanceV2(
            provider=provider,
            provider_symbol=provider_symbol,
            provider_exchange=exchange,
            source_type="LIVE",
            observed_at=observed_at,
            received_at=received_at,
            is_cached=False,
        )

        return MarketQuoteV2(
            quote_id=classification.identity.identity_sha256,
            market_symbol=market_symbol,
            exchange=exchange,
            instrument_type=instrument_type,
            canonical_instrument_id=canonical_id,
            last_price=ltp,
            bid_price=None,
            ask_price=None,
            volume=None,
            open_interest=None,
            provenance=provenance,
        )


__all__ = [
    "BridgeResultV1",
    "StreamingHubBridgeError",
    "StreamingHubBridgeV1",
]

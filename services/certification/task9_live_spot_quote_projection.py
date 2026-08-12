"""Provider-free Task 9 projection of certified Angel spot evidence."""

from __future__ import annotations

from services.contracts.market_data_provenance_v1 import (
    MarketDataProvenanceV1,
)
from services.contracts.market_data_quality_result_v1 import (
    MarketDataQualityResultV1,
)
from services.contracts.market_quote_v1 import (
    MarketQuoteV1,
)
from services.data_quality.freshness import (
    evaluate_quote_freshness,
)
from services.market.angel_live_observation_normalizer import (
    AngelLiveSpotObservationV1,
)


def project_task9_live_spot_quote(
    *,
    spot: AngelLiveSpotObservationV1,
) -> MarketQuoteV1:
    """Project already-normalized Angel spot evidence without provider reads."""

    if type(spot) is not AngelLiveSpotObservationV1:
        raise TypeError(
            "spot must be exact AngelLiveSpotObservationV1"
        )

    if spot.price is None:
        raise ValueError(
            "Task 9 quote requires available spot price"
        )

    if spot.provider_timestamp is None:
        raise ValueError(
            "Task 9 quote requires provider timestamp"
        )

    provenance = MarketDataProvenanceV1(
        provider="ANGEL_ONE",
        provider_symbol=spot.underlying_symbol,
        provider_exchange=spot.exchange,
        source_type="LIVE",
        fetched_at=spot.provider_timestamp,
        received_at=spot.evaluated_at,
        is_cached=False,
        cache_age_seconds=None,
        provider_request_id=None,
        warnings=spot.warnings,
    )

    return MarketQuoteV1(
        quote_id=(
            "task9-live-spot:"
            f"{spot.underlying_symbol}:"
            f"{spot.exchange}:"
            f"{spot.provider_timestamp.isoformat()}"
        ),
        underlying_symbol=spot.underlying_symbol,
        exchange=spot.exchange,
        observed_at=spot.provider_timestamp,
        received_at=spot.evaluated_at,
        last_price=spot.price,
        previous_close=None,
        open_price=None,
        high_price=None,
        low_price=None,
        volume=None,
        bid_price=None,
        ask_price=None,
        provenance=provenance,
        execution_mode="PAPER",
        live_execution_eligible=False,
        warnings=tuple(
            dict.fromkeys(
                (
                    *spot.warnings,
                    *spot.blockers,
                )
            )
        ),
    )


def evaluate_task9_live_spot_quote_quality(
    *,
    quote: MarketQuoteV1,
) -> MarketDataQualityResultV1:
    """Evaluate quote freshness at its certified receipt boundary."""

    if type(quote) is not MarketQuoteV1:
        raise TypeError(
            "quote must be exact MarketQuoteV1"
        )

    return evaluate_quote_freshness(
        quote,
        clock=lambda: quote.received_at,
        quality_result_id_factory=lambda: (
            f"{quote.quote_id}:quality"
        ),
    )


def project_task9_live_spot_quote_with_quality(
    *,
    spot: AngelLiveSpotObservationV1,
) -> tuple[
    MarketQuoteV1,
    MarketDataQualityResultV1,
]:
    """Project one certified quote and its quote-specific quality result."""

    quote = project_task9_live_spot_quote(
        spot=spot,
    )

    quality = (
        evaluate_task9_live_spot_quote_quality(
            quote=quote,
        )
    )

    return quote, quality
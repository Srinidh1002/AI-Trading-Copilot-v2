"""Task 9 Angel spot FULL proof production from canonical quotes.

This module performs no provider acquisition.

It converts the already validated canonical NIFTY/SENSEX FULL quote
authority into immutable Task 9 startup-proof contracts.

Provider acquisition remains owned by
services.broker.two_market_quote_service.
"""
from __future__ import annotations

from services.broker.two_market_quote_service import (
    CanonicalIndexFullQuote,
    CanonicalTwoMarketFullQuotes,
)
from services.contracts.task9_angel_spot_full_proof_v1 import (
    Task9AngelSpotFullProbeStatus,
    Task9AngelSpotFullProofV1,
)


def _proof_id(
    quote: CanonicalIndexFullQuote,
) -> str:
    stamp = quote.received_at.isoformat()

    return (
        "task9-angel-spot-full:"
        f"{quote.market}:"
        f"{quote.exchange}:"
        f"{quote.symboltoken}:"
        f"{stamp}"
    )


def _build_proof(
    quote: CanonicalIndexFullQuote,
) -> Task9AngelSpotFullProofV1:
    if type(quote) is not CanonicalIndexFullQuote:
        raise TypeError("quote")

    return Task9AngelSpotFullProofV1(
        proof_id=_proof_id(quote),
        observed_at=quote.received_at,
        market=quote.market,
        exchange=quote.exchange,
        token=quote.symboltoken,
        status=(
            Task9AngelSpotFullProbeStatus.AVAILABLE
        ),
        provider_timestamp=(
            quote.provider_timestamp
        ),
        ltp=quote.ltp,
        identity_verified=True,
        source_ref=(
            "canonical-two-market-full:"
            f"{quote.market}:"
            f"{quote.exchange}:"
            f"{quote.symboltoken}"
        ),
        incident_ref=None,
        sanitized_reason=None,
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


def produce_task9_angel_spot_full_proofs(
    full_quotes: CanonicalTwoMarketFullQuotes,
) -> tuple[
    Task9AngelSpotFullProofV1,
    Task9AngelSpotFullProofV1,
]:
    """Produce NIFTY then SENSEX proof from one canonical quote bundle."""

    if (
        type(full_quotes)
        is not CanonicalTwoMarketFullQuotes
    ):
        raise TypeError("full_quotes")

    proofs = tuple(
        _build_proof(quote)
        for quote in full_quotes.ordered()
    )

    if tuple(
        proof.market
        for proof in proofs
    ) != (
        "NIFTY",
        "SENSEX",
    ):
        raise ValueError(
            "TASK9_SPOT_FULL_PROOF_ORDER_INVALID"
        )

    return proofs


__all__ = (
    "produce_task9_angel_spot_full_proofs",
)

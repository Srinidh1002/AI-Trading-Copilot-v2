from datetime import datetime, timedelta, timezone

import pytest

from services.broker.two_market_quote_service import (
    CanonicalIndexFullQuote,
    CanonicalTwoMarketFullQuotes,
)
from services.certification.task9_angel_spot_full_proof_producer import (
    produce_task9_angel_spot_full_proofs,
)
from services.contracts.task9_angel_spot_full_proof_v1 import (
    Task9AngelSpotFullProbeStatus,
)


NOW = datetime(
    2026,
    8,
    17,
    5,
    5,
    0,
    tzinfo=timezone.utc,
)


def _quote(
    *,
    market,
    exchange,
    token,
    symbol,
    ltp,
):
    provider_timestamp = NOW - timedelta(
        seconds=1
    )

    return CanonicalIndexFullQuote(
        market=market,
        exchange=exchange,
        symboltoken=token,
        tradingsymbol=symbol,
        ltp=ltp,
        provider_timestamp=provider_timestamp,
        received_at=NOW,
        timestamp_field="exchangeTimeStamp",
        quote_age_seconds=1.0,
        payload={
            "exchange": exchange,
            "symbolToken": token,
            "tradingSymbol": symbol,
            "ltp": ltp,
        },
    )


def _bundle():
    return CanonicalTwoMarketFullQuotes(
        nifty=_quote(
            market="NIFTY",
            exchange="NSE",
            token="99926000",
            symbol="Nifty 50",
            ltp=24582.15,
        ),
        sensex=_quote(
            market="SENSEX",
            exchange="BSE",
            token="99919000",
            symbol="SENSEX",
            ltp=78623.26,
        ),
    )


def test_produces_nifty_and_sensex_available_proofs():
    proofs = (
        produce_task9_angel_spot_full_proofs(
            _bundle()
        )
    )

    assert tuple(
        proof.market
        for proof in proofs
    ) == (
        "NIFTY",
        "SENSEX",
    )

    assert all(
        proof.status
        is Task9AngelSpotFullProbeStatus.AVAILABLE
        for proof in proofs
    )


def test_nifty_proof_maps_exact_canonical_quote():
    bundle = _bundle()

    nifty, _ = (
        produce_task9_angel_spot_full_proofs(
            bundle
        )
    )

    quote = bundle.nifty

    assert nifty.observed_at == quote.received_at
    assert (
        nifty.provider_timestamp
        == quote.provider_timestamp
    )
    assert nifty.market == quote.market
    assert nifty.exchange == quote.exchange
    assert nifty.token == quote.symboltoken
    assert nifty.ltp == quote.ltp
    assert nifty.identity_verified is True


def test_sensex_proof_maps_exact_canonical_quote():
    bundle = _bundle()

    _, sensex = (
        produce_task9_angel_spot_full_proofs(
            bundle
        )
    )

    quote = bundle.sensex

    assert sensex.observed_at == quote.received_at
    assert (
        sensex.provider_timestamp
        == quote.provider_timestamp
    )
    assert sensex.market == quote.market
    assert sensex.exchange == quote.exchange
    assert sensex.token == quote.symboltoken
    assert sensex.ltp == quote.ltp
    assert sensex.identity_verified is True


def test_proof_preserves_paper_only_safety():
    proofs = (
        produce_task9_angel_spot_full_proofs(
            _bundle()
        )
    )

    for proof in proofs:
        assert proof.execution_mode == "PAPER"
        assert (
            proof.broker_order_submission
            is False
        )
        assert (
            proof.live_execution_eligible
            is False
        )


def test_proof_has_no_failure_or_incident_on_valid_quote():
    proofs = (
        produce_task9_angel_spot_full_proofs(
            _bundle()
        )
    )

    for proof in proofs:
        assert proof.incident_ref is None
        assert proof.sanitized_reason is None


def test_source_ref_contains_only_canonical_identity():
    nifty, sensex = (
        produce_task9_angel_spot_full_proofs(
            _bundle()
        )
    )

    assert nifty.source_ref == (
        "canonical-two-market-full:"
        "NIFTY:NSE:99926000"
    )

    assert sensex.source_ref == (
        "canonical-two-market-full:"
        "SENSEX:BSE:99919000"
    )


def test_proof_ids_are_deterministic_for_same_bundle():
    first = (
        produce_task9_angel_spot_full_proofs(
            _bundle()
        )
    )

    second = (
        produce_task9_angel_spot_full_proofs(
            _bundle()
        )
    )

    assert tuple(
        proof.proof_id
        for proof in first
    ) == tuple(
        proof.proof_id
        for proof in second
    )


def test_rejects_noncanonical_bundle_type():
    with pytest.raises(
        TypeError,
        match="full_quotes",
    ):
        produce_task9_angel_spot_full_proofs(
            object()
        )


def test_producer_is_pure_and_does_not_require_market_client():
    bundle = _bundle()

    proofs = (
        produce_task9_angel_spot_full_proofs(
            bundle
        )
    )

    assert len(proofs) == 2

    # The producer accepts only retained canonical quotes.
    # There is no market-client/provider argument and therefore
    # no second FULL request can be issued from this authority.
    import inspect

    parameters = inspect.signature(
        produce_task9_angel_spot_full_proofs
    ).parameters

    assert tuple(parameters) == (
        "full_quotes",
    )

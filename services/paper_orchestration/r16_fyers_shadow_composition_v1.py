"""FYERS-only composition for the R16 NIFTY/SENSEX SHADOW selector.

This builder is intentionally independent from the active R15 workers. It
constructs read-only quote/candle/native-option/canonical-candidate authorities
for one observational parent cycle. No sockets, broker orders, PAPER lifecycle
writes, or certification counters are owned here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from services.broker.fyers_data_compatibility_v2 import (
    FyersDataOnlyCompatibilityV2,
)
from services.broker.fyers_five_market_resolver_v2 import (
    FyersFiveMarketInstrumentResolverV2,
)
from services.broker.fyers_legacy_identity_resolver_v2 import (
    FyersLegacyIdentityResolverV2,
)
from services.broker.fyers_provider_adapters_v2 import (
    FyersQuoteDepthProviderV2,
)
from services.live_analysis_pipeline import LiveAnalysisPipeline
from services.market.live_multi_timeframe_data import LiveMultiTimeframeData
from services.options.fyers_native_option_chain_engine_v2 import (
    FyersNativeOptionChainEngineV2,
)
from services.options.fyers_option_chain_provider_v2 import (
    FyersOptionChainProviderV2,
)
from services.options.r16_fyers_native_option_capture_v1 import (
    R16FyersNativeOptionCapturePipelineV1,
    load_legacy_index_option_instruments,
)
from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
)
from services.paper_orchestration.certified_runtime_composition import (
    capture_certified_live_evidence,
)
from services.paper_orchestration.r16_canonical_candidate_reader_v1 import (
    R16CanonicalCandidateReaderV1,
)


def _as_aware_timestamp(value: object, *, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider timestamp must be timezone-aware")
        return value

    if isinstance(value, str) and value.strip():
        try:
            value = float(value.strip())
        except ValueError:
            value = None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OSError, ValueError, OverflowError) as exc:
            raise ValueError("provider timestamp invalid") from exc

    # Never invent an exchange timestamp. A missing provider timestamp is
    # surfaced explicitly by the quote reader as a blocker via exception.
    raise ValueError("provider timestamp missing")


def build_r16_fyers_shadow_readers_v1(
    *,
    data_client,
    instrument_rows,
    legacy_instrument_path: str | Path,
    available_capital: float = 100_000.0,
    clock=None,
    historical_cache=None,
    india_vix_reader=None,
    external_context_reader=None,
    substage_callback=None,
) -> CertifiedLiveProviderReaders:
    """Build one FYERS-only, read-only NIFTY/SENSEX shadow reader bundle."""

    if data_client is None:
        raise ValueError("data_client")
    if getattr(data_client, "data_only", None) is not True:
        raise ValueError("FYERS data-only client required")
    if getattr(data_client, "order_capability_allowed", None) is not False:
        raise ValueError("order capability prohibited")
    if getattr(data_client, "automatic_fallback_allowed", None) is not False:
        raise ValueError("automatic fallback prohibited")

    now = clock or (lambda: datetime.now(timezone.utc))
    if not callable(now):
        raise TypeError("clock")

    resolver = FyersFiveMarketInstrumentResolverV2(
        data_client=data_client,
        clock=now,
    )
    legacy_resolver = FyersLegacyIdentityResolverV2(
        instrument_rows=instrument_rows,
        resolver=resolver,
        clock=now,
    )
    compatibility = FyersDataOnlyCompatibilityV2(
        client=data_client,
        symbol_resolver=legacy_resolver,
    )

    data_service = LiveMultiTimeframeData(
        client=compatibility,
        cache=historical_cache,
    )
    analysis_pipeline = LiveAnalysisPipeline(
        data_service=data_service,
    )

    native_provider = FyersOptionChainProviderV2(
        data_client,
    )
    engines = {
        market: FyersNativeOptionChainEngineV2(
            market=market,
            provider=native_provider,
            resolver=resolver,
            legacy_identity_resolver=legacy_resolver,
            clock=now,
        )
        for market in ("NIFTY", "SENSEX")
    }
    instruments_by_market = load_legacy_index_option_instruments(
        legacy_instrument_path
    )
    option_capture = R16FyersNativeOptionCapturePipelineV1(
        engines_by_market=engines,
        resolver=resolver,
        instruments_by_market=instruments_by_market,
        clock=now,
    )

    quote_provider = FyersQuoteDepthProviderV2(
        data_client,
    )

    def quote_reader(exchange, _token, underlying_symbol):
        received_at = now()
        if (
            not isinstance(received_at, datetime)
            or received_at.tzinfo is None
            or received_at.utcoffset() is None
        ):
            raise ValueError("clock must return timezone-aware datetime")

        instrument = resolver.resolve(
            market_symbol=underlying_symbol,
            instrument_type="UNDERLYING",
            as_of=received_at,
        )
        quote = quote_provider.get_quote(instrument)
        market_timestamp = _as_aware_timestamp(
            quote.get("provider_timestamp"),
            fallback=received_at,
        )
        return {
            "spot_price": quote["last_price"],
            "market_timestamp": market_timestamp,
            "received_at": received_at,
            "timestamp_source": "FYERS_QUOTES_TT",
            "provider": "FYERS",
            "provider_symbol": quote.get("provider_symbol"),
            "execution_mode": "PAPER",
            "live_execution_eligible": False,
            "broker_order_submission": False,
        }

    def capture_reader(cycle_input, *, candle_cutoff=None):
        return capture_certified_live_evidence(
            cycle_input=cycle_input,
            data_service=data_service,
            option_decision_pipeline=option_capture,
            candle_cutoff=candle_cutoff,
        )

    readers = CertifiedLiveProviderReaders(
        quote_reader=quote_reader,
        analysis_pipeline=analysis_pipeline,
        option_decision_pipeline=option_capture,
        available_capital=float(available_capital),
        candidate_reader=R16CanonicalCandidateReaderV1(),
        capture_reader=capture_reader,
        india_vix_reader=india_vix_reader,
        external_context_reader=external_context_reader,
        substage_callback=substage_callback,
    )

    # Explicit composition safety assertion.
    if (
        getattr(data_client, "order_capability_allowed", None) is not False
        or getattr(option_capture, "broker_order_submission", None) is not False
        or getattr(readers.candidate_reader, "mode", None) != "SHADOW_ONLY"
    ):
        raise RuntimeError("R16_FYERS_SHADOW_SAFETY_INVARIANT")

    return readers

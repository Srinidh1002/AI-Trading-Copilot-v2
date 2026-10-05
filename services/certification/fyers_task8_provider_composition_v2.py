"""FYERS data-only composition for the existing certified Task 8 selector.

This module changes provider plumbing only. The authoritative two-market
comparison, selected-market planning, PAPER lifecycle, persistence, and safety
contracts remain owned by the existing Task 8 composition.

Nothing in this module launches a runtime or grants PAPER/live authorization.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path

from services.broker.fyers_data_compatibility_v2 import (
    FyersDataOnlyCompatibilityV2,
)
from services.broker.fyers_five_market_resolver_v2 import (
    FyersFiveMarketInstrumentResolverV2,
)
from services.certification.task8_live_paper_default_composition import (
    build_task8_dependencies,
)
from services.historical_data_cache import HistoricalDataCache
from services.historical_provider_cooldown import HistoricalProviderCooldown
from services.historical_request_gate import HistoricalRequestGate
from services.live_analysis_pipeline import LiveAnalysisPipeline
from services.live_option_decision_pipeline import LiveOptionDecisionPipeline
from services.market.live_multi_timeframe_data import LiveMultiTimeframeData
from services.options.fyers_certified_option_chain_builder_v2 import (
    FyersCertifiedTwoIndexOptionChainBuilderV2,
)
from services.options.fyers_option_chain_provider_v2 import (
    FyersOptionChainProviderV2,
)
from services.paper_orchestration.certified_runtime_composition import (
    CertifiedRuntimeProviderBundleV1,
)
from services.task9_daily_historical_warmup_retry import (
    Task9DailyWarmupRetryStore,
)


_INDEX_BY_LEGACY_TOKEN = {
    "99926000": ("NIFTY", "NSE"),
    "99919000": ("SENSEX", "BSE"),
}


class FyersTask8CompositionError(RuntimeError):
    """FYERS Task 8 provider composition failed closed."""


class FyersHistoricalProviderCooldownV2(HistoricalProviderCooldown):
    """Same durable cooldown mechanics with truthful FYERS provenance."""

    PROVIDER = "FYERS"


def _aware_now() -> datetime:
    return datetime.now(UTC)


def _positive(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise FyersTask8CompositionError(name)
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise FyersTask8CompositionError(name) from exc
    if not isfinite(result) or result <= 0:
        raise FyersTask8CompositionError(name)
    return result


def _provider_timestamp(value: object) -> datetime:
    if isinstance(value, bool):
        raise FyersTask8CompositionError("FYERS_QUOTE_TIMESTAMP_INVALID")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise FyersTask8CompositionError(
            "FYERS_QUOTE_TIMESTAMP_INVALID"
        ) from exc
    if not isfinite(numeric) or numeric <= 0:
        raise FyersTask8CompositionError("FYERS_QUOTE_TIMESTAMP_INVALID")
    if numeric > 100_000_000_000:
        numeric /= 1000.0
    try:
        return datetime.fromtimestamp(numeric, tz=UTC)
    except (OSError, OverflowError, ValueError) as exc:
        raise FyersTask8CompositionError(
            "FYERS_QUOTE_TIMESTAMP_INVALID"
        ) from exc


def build_fyers_legacy_index_symbol_resolver_v2(
    *,
    resolver,
    clock: Callable[[], datetime],
):
    """Resolve legacy index tokens through the authoritative FYERS resolver."""

    if resolver is None or not callable(getattr(resolver, "resolve", None)):
        raise TypeError("resolver")
    if not callable(clock):
        raise TypeError("clock")

    def resolve(
        exchange: str,
        tradingsymbol: str | None,
        symboltoken: str,
    ) -> str:
        token = str(symboltoken or "").strip()
        expected = _INDEX_BY_LEGACY_TOKEN.get(token)
        if expected is None:
            raise FyersTask8CompositionError(
                "UNSUPPORTED_LEGACY_INDEX_TOKEN"
            )

        market, expected_exchange = expected
        if str(exchange or "").strip().upper() != expected_exchange:
            raise FyersTask8CompositionError(
                "LEGACY_INDEX_EXCHANGE_MISMATCH"
            )

        supplied_symbol = str(tradingsymbol or "").strip().upper()
        if supplied_symbol and supplied_symbol != market:
            raise FyersTask8CompositionError(
                "LEGACY_INDEX_SYMBOL_MISMATCH"
            )

        now = clock()
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise FyersTask8CompositionError("CLOCK_NOT_TIMEZONE_AWARE")

        value = resolver.resolve(
            market_symbol=market,
            instrument_type="UNDERLYING",
            as_of=now,
        )
        if not isinstance(value, Mapping):
            raise FyersTask8CompositionError(
                "FYERS_UNDERLYING_RESOLUTION_INVALID"
            )

        provider_symbol = str(
            value.get("provider_symbol") or ""
        ).strip()
        if not provider_symbol:
            raise FyersTask8CompositionError(
                "FYERS_UNDERLYING_SYMBOL_MISSING"
            )
        return provider_symbol

    return resolve


def build_fyers_parent_quote_reader_v2(
    *,
    legacy_data_api: FyersDataOnlyCompatibilityV2,
    clock: Callable[[], datetime],
    maximum_quote_age_seconds: float = 300.0,
    maximum_future_skew_seconds: float = 5.0,
):
    """Return the exact parent quote shape expected by Task 8."""

    if type(legacy_data_api) is not FyersDataOnlyCompatibilityV2:
        raise TypeError("legacy_data_api")
    if not callable(clock):
        raise TypeError("clock")
    maximum_age = _positive(
        maximum_quote_age_seconds,
        "maximum_quote_age_seconds",
    )
    if (
        isinstance(maximum_future_skew_seconds, bool)
        or not isinstance(maximum_future_skew_seconds, (int, float))
        or not isfinite(float(maximum_future_skew_seconds))
        or float(maximum_future_skew_seconds) < 0
    ):
        raise ValueError("maximum_future_skew_seconds")
    future_skew = float(maximum_future_skew_seconds)

    def read(
        exchange: str,
        symboltoken: str,
        underlying: str,
    ) -> Mapping[str, object]:
        response = legacy_data_api.ltpData(
            exchange,
            underlying,
            symboltoken,
        )
        if not isinstance(response, Mapping) or response.get("status") is not True:
            raise FyersTask8CompositionError(
                "FYERS_PARENT_QUOTE_UNAVAILABLE"
            )
        data = response.get("data")
        if not isinstance(data, Mapping):
            raise FyersTask8CompositionError(
                "FYERS_PARENT_QUOTE_MALFORMED"
            )

        expected_exchange = str(exchange or "").strip().upper()
        expected_symbol = str(underlying or "").strip().upper()
        expected_token = str(symboltoken or "").strip()

        actual_exchange = str(data.get("exchange") or "").strip().upper()
        actual_symbol = str(
            data.get("tradingsymbol") or data.get("symbol") or ""
        ).strip().upper()
        actual_token = str(
            data.get("symboltoken") or data.get("symbolToken") or ""
        ).strip()

        if (
            actual_exchange,
            actual_symbol,
            actual_token,
        ) != (
            expected_exchange,
            expected_symbol,
            expected_token,
        ):
            raise FyersTask8CompositionError(
                "FYERS_PARENT_QUOTE_IDENTITY_MISMATCH"
            )

        ltp = _positive(
            data.get("ltp", data.get("last_price")),
            "FYERS_PARENT_QUOTE_LTP_INVALID",
        )
        timestamp_value = data.get(
            "exchange_timestamp",
            data.get("timestamp"),
        )
        market_timestamp = _provider_timestamp(timestamp_value)

        received_at = clock()
        if (
            not isinstance(received_at, datetime)
            or received_at.tzinfo is None
            or received_at.utcoffset() is None
        ):
            raise FyersTask8CompositionError("CLOCK_NOT_TIMEZONE_AWARE")

        age_seconds = (
            received_at.astimezone(UTC)
            - market_timestamp
        ).total_seconds()
        if age_seconds > maximum_age:
            raise FyersTask8CompositionError(
                "FYERS_PARENT_QUOTE_STALE"
            )
        if age_seconds < -future_skew:
            raise FyersTask8CompositionError(
                "FYERS_PARENT_QUOTE_FUTURE_SKEW"
            )

        return {
            "provider": "FYERS",
            "spot_price": ltp,
            "ltp": ltp,
            "market_timestamp": market_timestamp,
            "received_at": received_at,
            "timestamp_source": "FYERS_PROVIDER_TT",
            "provider_timestamp_field": "tt",
            "quote_age_seconds": age_seconds,
            "provider_response": dict(response),
        }

    return read


def build_fyers_task8_provider_bundle_v2(
    *,
    data_client,
    master_store=None,
    state_root: str | Path = "data/provider_cache/fyers_task8",
    clock: Callable[[], datetime] | None = None,
) -> CertifiedRuntimeProviderBundleV1:
    """Compose the existing certified analysis stack on FYERS data only."""

    if data_client is None:
        raise ValueError("data_client")
    clock_value = clock or _aware_now
    if not callable(clock_value):
        raise TypeError("clock")

    root = Path(state_root)
    resolver = FyersFiveMarketInstrumentResolverV2(
        data_client=data_client,
        master_store=master_store,
        clock=clock_value,
    )
    legacy_resolver = build_fyers_legacy_index_symbol_resolver_v2(
        resolver=resolver,
        clock=clock_value,
    )
    legacy_data_api = FyersDataOnlyCompatibilityV2(
        client=data_client,
        symbol_resolver=legacy_resolver,
    )

    cache = HistoricalDataCache(
        root / "historical_data_cache.json"
    )
    cooldown = FyersHistoricalProviderCooldownV2(
        root / "historical_provider_cooldown.json"
    )
    request_gate = HistoricalRequestGate(
        root / "historical_request_gate.json",
        interval_seconds=1.0,
    )
    retry_store = Task9DailyWarmupRetryStore(
        root / "daily_historical_warmup_retry.json"
    )

    data_service = LiveMultiTimeframeData(
        client=legacy_data_api,
        cache=cache,
        provider_cooldown=cooldown,
        historical_request_gate=request_gate,
        task9_daily_warmup_retry_store=retry_store,
        cache_enabled=False,
        provider_source="FYERS_HISTORICAL",
    )
    analysis_pipeline = LiveAnalysisPipeline(
        data_service=data_service,
    )

    option_provider = FyersOptionChainProviderV2(
        data_client
    )
    option_builder = FyersCertifiedTwoIndexOptionChainBuilderV2(
        provider=option_provider,
        resolver=resolver,
        clock=clock_value,
    )
    option_pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=option_builder,
        market_client=legacy_data_api,
        persist_audit=False,
    )
    quote_reader = build_fyers_parent_quote_reader_v2(
        legacy_data_api=legacy_data_api,
        clock=clock_value,
    )

    bundle = CertifiedRuntimeProviderBundleV1(
        quote_reader=quote_reader,
        analysis_pipeline=analysis_pipeline,
        option_decision_pipeline=option_pipeline,
        clock=clock_value,
    )

    if getattr(legacy_data_api, "data_only", None) is not True:
        raise FyersTask8CompositionError("FYERS_DATA_API_NOT_DATA_ONLY")
    if getattr(legacy_data_api, "order_capability_allowed", None) is not False:
        raise FyersTask8CompositionError(
            "FYERS_DATA_API_ORDER_CAPABILITY_PROHIBITED"
        )
    if getattr(option_builder, "data_only", None) is not True:
        raise FyersTask8CompositionError("FYERS_OPTION_BUILDER_NOT_DATA_ONLY")
    if getattr(option_builder, "order_capability_allowed", None) is not False:
        raise FyersTask8CompositionError(
            "FYERS_OPTION_BUILDER_ORDER_CAPABILITY_PROHIBITED"
        )

    return bundle


def build_fyers_task8_dependencies_v2(
    *,
    data_client,
    preflight_authority,
    master_store=None,
    state_root: str | Path = "data/provider_cache/fyers_task8",
    clock: Callable[[], datetime] | None = None,
):
    """Build, but never run, Task 8 dependencies using FYERS evidence.

    The caller must supply the existing release/preflight authority. This
    function does not infer authorization, mutate campaign state, or launch
    the canary.
    """

    if not callable(preflight_authority):
        raise TypeError("preflight_authority")

    bundle = build_fyers_task8_provider_bundle_v2(
        data_client=data_client,
        master_store=master_store,
        state_root=state_root,
        clock=clock,
    )

    return build_task8_dependencies(
        providers=bundle,
        parent_quote_reader=bundle.quote_reader,
        preflight_override=preflight_authority,
    )

"""FYERS data-only provider composition for the certified two-index PAPER path."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from services.analysis.live_market_candidate_evaluator import (
    LiveMarketCandidateEvaluationResultV1,
)
from services.broker.fyers_data_compatibility_v2 import (
    FyersDataOnlyCompatibilityV2,
)
from services.broker.fyers_legacy_identity_resolver_v2 import (
    FyersLegacyIdentityResolverV2,
)
from services.live_analysis_pipeline import LiveAnalysisPipeline
from services.market.live_multi_timeframe_data import LiveMultiTimeframeData
from services.options.fyers_certified_option_capture_v2 import (
    FyersCertifiedOptionCaptureError,
    FyersCertifiedOptionCaptureV2,
)
from services.options.fyers_option_chain_provider_v2 import (
    FyersOptionChainProviderV2,
)
from services.paper_orchestration.certified_runtime_composition import (
    CertifiedRuntimeProviderBundleV1,
)


IST = ZoneInfo("Asia/Kolkata")


class FyersCertifiedProviderCompositionError(RuntimeError):
    """FYERS certified provider composition failed closed."""


def _aware_clock(clock) -> datetime:
    value = clock()
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("clock must return timezone-aware datetime")
    return value


def _provider_timestamp(value: object) -> datetime:
    if isinstance(value, bool):
        raise ValueError("FYERS provider timestamp invalid")
    try:
        epoch = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("FYERS provider timestamp missing") from exc
    if epoch <= 0:
        raise ValueError("FYERS provider timestamp invalid")
    return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(IST)


class FyersCertifiedIndexOptionPipelineV2:
    """Dispatch certified option capture to the exact index adapter."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(self, *, nifty, sensex) -> None:
        if type(nifty) is not FyersCertifiedOptionCaptureV2:
            raise TypeError("nifty")
        if type(sensex) is not FyersCertifiedOptionCaptureV2:
            raise TypeError("sensex")
        self._by_market = {
            "NIFTY": nifty,
            "SENSEX": sensex,
        }

    def analyse(self, *args, **kwargs):
        raise FyersCertifiedOptionCaptureError(
            "FYERS_CERTIFIED_CAPTURE_ONLY"
        )

    def capture_option_inputs(self, *, underlying, **kwargs):
        market = str(underlying or "").strip().upper()
        adapter = self._by_market.get(market)
        if adapter is None:
            raise ValueError("unsupported certified FYERS index market")
        return adapter.capture_option_inputs(
            underlying=market,
            **kwargs,
        )


def build_fyers_certified_runtime_providers_v2(
    *,
    data_client,
    resolver,
    instrument_rows: Sequence[Mapping[str, object]],
    clock: Callable[[], datetime] | None = None,
    cache_enabled: bool = True,
    historical_request_interval_seconds: float | None = None,
    maximum_quote_age_seconds: float = 30.0,
    maximum_future_skew_seconds: float = 5.0,
) -> CertifiedRuntimeProviderBundleV1:
    """Build the existing certified two-index analysis contracts on FYERS.

    This is a data-only composition. It neither creates authentication nor
    exposes order methods or automatic provider fallback.
    """
    if data_client is None:
        raise ValueError("data_client")
    if resolver is None or not callable(getattr(resolver, "resolve", None)):
        raise TypeError("resolver")
    if (
        not isinstance(instrument_rows, Sequence)
        or isinstance(instrument_rows, (str, bytes))
    ):
        raise TypeError("instrument_rows")
    if not isinstance(cache_enabled, bool):
        raise TypeError("cache_enabled")

    clock = clock or (lambda: datetime.now(timezone.utc))
    now = lambda: _aware_clock(clock)

    legacy_resolver = FyersLegacyIdentityResolverV2(
        instrument_rows=instrument_rows,
        resolver=resolver,
        clock=now,
    )
    compatibility = FyersDataOnlyCompatibilityV2(
        client=data_client,
        symbol_resolver=legacy_resolver,
    )

    data_kwargs = {
        "client": compatibility,
        "cache_enabled": cache_enabled,
    }
    if historical_request_interval_seconds is not None:
        data_kwargs["historical_request_interval_seconds"] = (
            historical_request_interval_seconds
        )

    data_service = LiveMultiTimeframeData(**data_kwargs)
    analysis_pipeline = LiveAnalysisPipeline(
        data_service=data_service,
    )

    native_provider = FyersOptionChainProviderV2(
        data_client,
        clock=now,
    )
    option_pipeline = FyersCertifiedIndexOptionPipelineV2(
        nifty=FyersCertifiedOptionCaptureV2(
            market="NIFTY",
            provider=native_provider,
            resolver=resolver,
            clock=now,
        ),
        sensex=FyersCertifiedOptionCaptureV2(
            market="SENSEX",
            provider=native_provider,
            resolver=resolver,
            clock=now,
        ),
    )

    max_age = float(maximum_quote_age_seconds)
    max_future = float(maximum_future_skew_seconds)
    if max_age < 0 or max_future < 0:
        raise ValueError("quote age/skew limits must be non-negative")

    def quote_reader(
        exchange: str,
        symboltoken: str,
        underlying: str,
    ) -> Mapping[str, object]:
        response = compatibility.get_ltp(
            exchange,
            underlying,
            symboltoken,
        )
        if not isinstance(response, Mapping) or response.get("status") is not True:
            raise FyersCertifiedProviderCompositionError(
                "FYERS_SPOT_QUOTE_FAILED"
            )
        data = response.get("data")
        if not isinstance(data, Mapping):
            raise FyersCertifiedProviderCompositionError(
                "FYERS_SPOT_QUOTE_DATA_MISSING"
            )

        expected_exchange = str(exchange).strip().upper()
        expected_underlying = str(underlying).strip().upper()
        expected_token = str(symboltoken).strip()

        if str(data.get("exchange") or "").strip().upper() != expected_exchange:
            raise FyersCertifiedProviderCompositionError(
                "FYERS_SPOT_EXCHANGE_MISMATCH"
            )
        if (
            str(data.get("tradingsymbol") or "").strip().upper()
            != expected_underlying
        ):
            raise FyersCertifiedProviderCompositionError(
                "FYERS_SPOT_SYMBOL_MISMATCH"
            )
        if str(data.get("symboltoken") or "").strip() != expected_token:
            raise FyersCertifiedProviderCompositionError(
                "FYERS_SPOT_TOKEN_MISMATCH"
            )

        try:
            spot = float(data.get("ltp"))
        except (TypeError, ValueError) as exc:
            raise FyersCertifiedProviderCompositionError(
                "FYERS_SPOT_PRICE_INVALID"
            ) from exc
        if spot <= 0:
            raise FyersCertifiedProviderCompositionError(
                "FYERS_SPOT_PRICE_INVALID"
            )

        market_timestamp = _provider_timestamp(
            data.get("exchange_timestamp", data.get("timestamp"))
        )
        received_at = now()
        age = (received_at - market_timestamp).total_seconds()

        if age < -max_future:
            raise FyersCertifiedProviderCompositionError(
                "FYERS_SPOT_TIMESTAMP_FUTURE"
            )
        if age > max_age:
            raise FyersCertifiedProviderCompositionError(
                "FYERS_SPOT_TIMESTAMP_STALE"
            )

        return {
            "provider": "FYERS",
            "spot_price": spot,
            "ltp": spot,
            "market_timestamp": market_timestamp,
            "received_at": received_at,
            "timestamp_source": "FYERS_PROVIDER_EXCHANGE_TIMESTAMP",
            "provider_timestamp_field": "exchange_timestamp",
            "quote_age_seconds": max(0.0, age),
            "provider_response": dict(response),
        }

    bundle = CertifiedRuntimeProviderBundleV1(
        quote_reader=quote_reader,
        analysis_pipeline=analysis_pipeline,
        option_decision_pipeline=option_pipeline,
        clock=now,
        provider_name="FYERS",
        data_only=True,
        order_capability_allowed=False,
        automatic_fallback_allowed=False,
    )

    # Explicit post-composition safety assertions prevent a permissive injected
    # object from silently widening this provider boundary.
    if compatibility.data_only is not True:
        raise FyersCertifiedProviderCompositionError(
            "FYERS_COMPATIBILITY_NOT_DATA_ONLY"
        )
    if compatibility.order_capability_allowed is not False:
        raise FyersCertifiedProviderCompositionError(
            "FYERS_ORDER_CAPABILITY_PROHIBITED"
        )
    if compatibility.automatic_fallback_allowed is not False:
        raise FyersCertifiedProviderCompositionError(
            "FYERS_AUTOMATIC_FALLBACK_PROHIBITED"
        )

    return bundle

"""Provider-injected UnifiedTradingBot path for FYERS data-only operation.

F12 deliberately leaves target_focused_bot.py unchanged. This subclass replaces
only provider startup/reconnect/stream ownership. Strategy, risk, PAPER lifecycle,
certification and decision code remain inherited byte-for-byte.

The legacy OptionChainEngine is intentionally NOT initialized here. F13 must wire
the native FYERS option-chain service so a chain batch cannot fan out into dozens
of per-contract depth calls.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from target_focused_bot import (
    EconomicCalendarEngine,
    EnhancedVIX,
    ExternalIntelEngine,
    FIIDIIEngine,
    MarketIntelligence,
    NewsEngine,
    PreviousDayEngine,
    UnifiedTradingBot,
)


class ProviderInjectedBotError(RuntimeError):
    """Provider injection failed closed."""


class _ProviderStreamingStatusV2:
    """Small compatibility facade for existing bot health reporting."""

    def __init__(self, streaming, subscription_id: str) -> None:
        self._streaming = streaming
        self._subscription_id = subscription_id
        self._closed = False

    def health_str(self) -> str:
        try:
            if hasattr(self._streaming, "is_healthy"):
                return "HEALTHY" if self._streaming.is_healthy(90) else "STALE"
            snapshot = self._streaming.snapshot()
            return "HEALTHY" if snapshot.get("connected") else "OFFLINE"
        except Exception:
            return "OFFLINE"

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._streaming.unsubscribe(self._subscription_id)
        except Exception:
            pass


class ProviderInjectedUnifiedTradingBotV2(UnifiedTradingBot):
    """UnifiedTradingBot with an externally supplied FYERS V2 runtime."""

    provider_mode = "FYERS_V2_INJECTED"
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        market="NIFTY",
        *,
        provider_runtime,
        legacy_data_api,
    ) -> None:
        super().__init__(market)
        self._validate_provider_boundary(provider_runtime, legacy_data_api)
        self._provider_runtime = provider_runtime
        self.obj = legacy_data_api
        self._provider_subscription_id = None
        self.provider_option_chain_status = "F13_NATIVE_OPTION_CHAIN_REQUIRED"

    @staticmethod
    def _validate_provider_boundary(runtime, data_api) -> None:
        if getattr(runtime, "provider", None) != "FYERS":
            raise ProviderInjectedBotError("FYERS_RUNTIME_REQUIRED")
        if getattr(runtime, "data_only", None) is not True:
            raise ProviderInjectedBotError("RUNTIME_NOT_DATA_ONLY")
        if getattr(runtime, "order_capability_allowed", None) is not False:
            raise ProviderInjectedBotError("RUNTIME_ORDER_CAPABILITY_PROHIBITED")
        if getattr(runtime, "automatic_fallback_allowed", None) is not False:
            raise ProviderInjectedBotError("RUNTIME_FALLBACK_PROHIBITED")
        if getattr(data_api, "data_only", None) is not True:
            raise ProviderInjectedBotError("DATA_API_NOT_DATA_ONLY")
        if getattr(data_api, "order_capability_allowed", None) is not False:
            raise ProviderInjectedBotError("DATA_API_ORDER_CAPABILITY_PROHIBITED")
        if getattr(data_api, "automatic_fallback_allowed", None) is not False:
            raise ProviderInjectedBotError("DATA_API_FALLBACK_PROHIBITED")

    def _initialize_provider_engines(self) -> None:
        """Initialize existing readers against the injected FYERS data API."""
        if self.market_intel is None:
            self.market_intel = MarketIntelligence(
                self.obj,
                self.market,
                rate_limiter=self.rate_limiter,
            )

        if self.vix_engine is None:
            self.vix_engine = EnhancedVIX(
                self.obj,
                rate_limiter=self.rate_limiter,
            )

        if self.calendar_engine is None:
            self.calendar_engine = EconomicCalendarEngine()
            self.calendar_engine.load_recurring()

        if self.news_engine is None:
            self.news_engine = NewsEngine(cache_ttl=1800)

        if self.fii_dii_engine is None:
            self.fii_dii_engine = FIIDIIEngine(cache_ttl=1800)

        if self.external_intel is None:
            self.external_intel = ExternalIntelEngine(cache_ttl=900)

        if self.prev_day_engine is None:
            self.prev_day_engine = PreviousDayEngine(
                self.obj,
                self.market,
                self.index_exchange,
                self.index_token,
                rate_limiter=self.rate_limiter,
            )

        # Deliberately fail closed until F13 native option-chain integration.
        self.option_chain_engine = None
        self.provider_option_chain_status = "F13_NATIVE_OPTION_CHAIN_REQUIRED"

    def connect_with_retry(self, max_retries=5, retry_delay=30):
        """Provider-safe startup; never enters the inherited Angel auth path."""
        for attempt in range(max_retries):
            try:
                print(
                    f"Provider connection attempt {attempt + 1}/{max_retries}..."
                )
                if not self.check_connection():
                    raise ProviderInjectedBotError("FYERS_PRIMARY_QUOTE_UNAVAILABLE")

                self._initialize_provider_engines()
                self.is_connected = True
                if self.ws_feed is None:
                    self._start_websocket()
                print("Connected successfully through FYERS V2 data runtime")
                return True
            except Exception as exc:
                self.is_connected = False
                print(f"Provider connection error: {str(exc)[:120]}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        return False

    def reconnect_if_needed(self):
        if self.check_connection():
            return True
        self.is_connected = False
        # Safe because this override never constructs SmartConnect.
        return self.connect_with_retry(max_retries=3, retry_delay=10)

    def _start_websocket(self):
        """Subscribe the existing candle builder to the FYERS V2 stream."""
        if self._provider_subscription_id is not None:
            return

        instrument = self._provider_runtime.resolver.resolve(
            market_symbol=self.market,
            instrument_type="UNDERLYING",
            as_of=datetime.now(timezone.utc),
        )

        def on_tick(tick):
            ltp = tick.get("ltp")
            ts = tick.get("ts")
            if ltp is None or ts is None:
                return
            self.candle_builder.on_tick(self.index_token, ltp, ts)
            self.ws_healthy = True

        subscription_id = self._provider_runtime.streaming.subscribe(
            (instrument,),
            on_tick,
        )

        if hasattr(self._provider_runtime.streaming, "wait_until_connected"):
            if not self._provider_runtime.streaming.wait_until_connected(8.0):
                try:
                    self._provider_runtime.streaming.unsubscribe(subscription_id)
                finally:
                    raise ProviderInjectedBotError("FYERS_STREAM_NOT_CONNECTED")

        self._provider_subscription_id = subscription_id
        self.ws_feed = _ProviderStreamingStatusV2(
            self._provider_runtime.streaming,
            subscription_id,
        )

    def close_provider_subscription(self) -> None:
        if self.ws_feed is not None and hasattr(self.ws_feed, "close"):
            self.ws_feed.close()
        self.ws_feed = None
        self._provider_subscription_id = None
        self.ws_healthy = False

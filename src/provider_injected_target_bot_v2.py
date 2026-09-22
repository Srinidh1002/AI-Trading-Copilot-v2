"""Provider-injected UnifiedTradingBot path for FYERS data-only operation.

The base target_focused_bot.py remains unchanged. This subclass replaces only
provider startup/reconnect/stream ownership and, when supplied, the option-chain
reader. Strategy, risk, PAPER lifecycle, certification and decision code remain
inherited.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from services.core.premarket_state_builder_v2 import build_premarket_state_v2
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

from services.broker.fyers_auth_v2 import (
    classify_fyers_exception_v2,
)
from services.broker.fyers_provider_runtime_v2 import (
    check_fyers_provider_health_v2,
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
        native_option_chain_engine=None,
    ) -> None:
        super().__init__(market)
        self._validate_provider_boundary(
            provider_runtime,
            legacy_data_api,
            native_option_chain_engine,
        )
        self._provider_runtime = provider_runtime
        self._native_option_chain_engine = native_option_chain_engine
        self.obj = legacy_data_api
        self._provider_subscription_id = None
        self.provider_option_chain_status = (
            "READY_NATIVE_FYERS"
            if native_option_chain_engine is not None
            else "F13_NATIVE_OPTION_CHAIN_REQUIRED"
        )

    def check_connection(self):
        """
        FYERS provider-aware connectivity check.

        Overrides the inherited Angel-shaped check_connection() which
        would otherwise return from a bare except: with no reason code.

        Preserves the truthy/falsy contract for connect_with_retry and
        reconnect_if_needed. Stores the last reason_code on the instance
        so callers and journals can distinguish AUTH_INVALID /
        AUTH_EXPIRED / NETWORK_ERROR / RATE_LIMIT / PROVIDER_ERROR /
        MALFORMED_RESPONSE.
        """
        self._last_health_reason_code = None
        self._last_health_provider_code = None

        client = getattr(self.obj, "_client", None)
        if client is None:
            self._last_health_reason_code = "PROVIDER_ERROR"
            return False

        try:
            health = check_fyers_provider_health_v2(client)
        except Exception as exc:
            err = classify_fyers_exception_v2(exc)
            self._last_health_reason_code = err.reason_code
            self._last_health_provider_code = err.provider_code
            return False

        self._last_health_reason_code = health.reason_code
        self._last_health_provider_code = health.provider_code
        return bool(health.ok)


    @staticmethod
    def _validate_provider_boundary(runtime, data_api, option_chain_engine=None) -> None:
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
        if option_chain_engine is not None:
            if getattr(option_chain_engine, "data_only", None) is not True:
                raise ProviderInjectedBotError("OPTION_CHAIN_NOT_DATA_ONLY")
            if getattr(option_chain_engine, "order_capability_allowed", None) is not False:
                raise ProviderInjectedBotError("OPTION_CHAIN_ORDER_CAPABILITY_PROHIBITED")
            if getattr(option_chain_engine, "automatic_fallback_allowed", None) is not False:
                raise ProviderInjectedBotError("OPTION_CHAIN_FALLBACK_PROHIBITED")

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

        native_chain = getattr(self, "_native_option_chain_engine", None)
        if native_chain is not None:
            self.option_chain_engine = native_chain
            self.provider_option_chain_status = "READY_NATIVE_FYERS"
        else:
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

    def _build_premarket_backfill(self):
        """Build canonical premarket evidence after an inherited early WAIT.

        The base analysis historically returns before its existing canonical
        premarket block when weighted-stock evidence is incomplete. This helper
        is observation/data plumbing only: it does not change that WAIT decision
        or any scoring threshold.
        """

        def _safe_fetch(engine):
            if engine is None or not hasattr(engine, "fetch"):
                return {}
            try:
                value = engine.fetch()
                return value if isinstance(value, dict) else {}
            except Exception:
                return {}

        previous_day = _safe_fetch(getattr(self, "prev_day_engine", None))
        external = _safe_fetch(getattr(self, "external_intel", None))
        vix = _safe_fetch(getattr(self, "vix_engine", None))
        fii_dii = _safe_fetch(getattr(self, "fii_dii_engine", None))

        event = {}
        calendar = getattr(self, "calendar_engine", None)
        if calendar is not None and hasattr(calendar, "minutes_to_next_high_impact"):
            try:
                value = calendar.minutes_to_next_high_impact(10)
                if isinstance(value, dict):
                    event = value
            except Exception:
                event = {}

        session_open = (
            getattr(self, "_day_open_value", None)
            if getattr(self, "_day_open_status", None) == "OK"
            else None
        )

        try:
            state = build_premarket_state_v2(
                market_symbol=self.market,
                generated_at=datetime.now().astimezone(),
                previous_day_payload=previous_day,
                session_open=session_open,
                external_payload=external,
                vix_payload=vix,
                fii_dii_payload=fii_dii,
                event_payload=event,
                event_source_authoritative=False,
            )
        except Exception:
            return None

        print(
            "[P8B.2] PremarketV2 backfill "
            f"prev={state.previous_session_status} "
            f"global={state.global_risk.evidence_status} "
            f"vix={state.volatility.evidence_status} "
            f"flow={state.institutional_flow.evidence_status} "
            f"event={state.event_risk.evidence_status}"
        )
        return state

    def get_enhanced_sentiment(self, spot, options):
        """Preserve inherited decisions while guaranteeing premarket observability."""
        result = super().get_enhanced_sentiment(spot, options)
        if getattr(self, "_last_premarket_state", None) is None:
            self._last_premarket_state = self._build_premarket_backfill()
        return result

    def get_expiry(self):
        """Use the production FYERS resolver as expiry tradability authority."""
        if getattr(self, "_native_option_chain_engine", None) is None:
            return super().get_expiry()

        candidates: list[tuple[datetime, str, dict]] = []
        for inst in self.instruments:
            if not isinstance(inst, dict):
                continue
            if inst.get("type") not in {"CE", "PE"}:
                continue
            expiry_text = str(inst.get("expiry") or "").strip().upper()
            try:
                expiry_dt = datetime.strptime(expiry_text, "%d%b%Y")
                strike = float(inst.get("strike"))
            except (TypeError, ValueError):
                continue
            if strike <= 0:
                continue
            candidates.append((expiry_dt, expiry_text, inst))

        candidates.sort(key=lambda item: item[0])
        seen = set()
        now = datetime.now(timezone.utc)
        for expiry_dt, expiry_text, representative in candidates:
            if expiry_text in seen:
                continue
            seen.add(expiry_text)
            try:
                self._provider_runtime.resolver.resolve(
                    market_symbol=self.market,
                    instrument_type="OPTION",
                    as_of=now,
                    expiry=expiry_dt.date(),
                    strike=float(representative["strike"]),
                    option_type=str(representative["type"]),
                )
            except Exception:
                continue
            print(f"  Expiry: {expiry_text}")
            print("  EXPIRY_SELECTION_SOURCE: FYERS_PRODUCTION_RESOLVER")
            return expiry_text

        print("  EXPIRY_SELECTION: EVIDENCE_UNAVAILABLE")
        return None

    def get_options(self, spot, expiry):
        """Read the initial option snapshot from the native FYERS chain cache."""
        native_chain = getattr(self, "_native_option_chain_engine", None)
        if native_chain is None:
            return super().get_options(spot, expiry)

        atm = round(spot / self.strike_interval) * self.strike_interval
        print(f"Spot: {spot}")
        print(f"ATM: {atm}")
        print(f"Expiry: {expiry}")
        if not expiry:
            self._last_chain = None
            return [], atm

        chain = native_chain.fetch(
            expiry,
            atm,
            self.instruments,
            strike_range=self.strike_interval * 3,
        )
        self._last_chain = chain
        if not chain or chain.get("status") != "OK":
            reason = chain.get("reason") if isinstance(chain, dict) else "UNKNOWN"
            print(f"  Native chain unavailable: {reason}")
            return [], atm

        options = []
        for opt_type, key in (("CE", "ce_data"), ("PE", "pe_data")):
            pool = chain.get(key) or {}
            for strike in sorted(pool):
                item = dict(pool[strike])
                ltp = float(item.get("ltp") or 0)
                if ltp <= 0:
                    continue
                options.append(item)
                print(f"  {opt_type} {strike}: ₹{ltp:.2f}")

        options.sort(key=lambda item: (float(item.get("strike") or 0), item.get("type")))
        print(f"Total options found: {len(options)}")
        print("OPTION_CHAIN_SOURCE: FYERS_NATIVE")
        print("OPTION_CHAIN_DEPTH_FANOUT: 0")
        return options, atm

    def close_provider_subscription(self) -> None:
        if self.ws_feed is not None and hasattr(self.ws_feed, "close"):
            self.ws_feed.close()
        self.ws_feed = None
        self._provider_subscription_id = None
        self.ws_healthy = False

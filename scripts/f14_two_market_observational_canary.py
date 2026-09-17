"""F14 bounded two-market observational canary.

Runs the existing provider-injected NIFTY/SENSEX analysis stack without calling
run_single_session(), without prediction-ledger persistence, without PAPER
state mutation and without any order API/socket.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import socket
import sys
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from provider_injected_target_bot_v2 import ProviderInjectedUnifiedTradingBotV2  # noqa: E402
from services.broker.angel_shadow_data_v2 import AngelShadowDataProviderV2  # noqa: E402
from services.broker.fyers_data_compatibility_v2 import FyersDataOnlyCompatibilityV2  # noqa: E402
from services.broker.fyers_legacy_identity_resolver_v2 import FyersLegacyIdentityResolverV2  # noqa: E402
from services.broker.fyers_provider_runtime_v2 import build_fyers_provider_runtime_v2  # noqa: E402
from services.broker.fyers_sdk_data_client_v2 import build_fyers_data_client_v2  # noqa: E402
from services.broker.fyers_streaming_v2 import FyersStreamingDataProviderV2  # noqa: E402
from services.broker.provider_registry_v2 import get_provider_registration  # noqa: E402
from services.broker.provider_shadow_parity_v2 import (  # noqa: E402
    AngelShadowIdentityV2,
    ProviderShadowParityEngineV2,
    ShadowParityThresholdsV2,
)
from services.core.provider_routing_policy_v2 import automatic_fallback_provider  # noqa: E402
from services.observation.two_market_canary_v2 import (  # noqa: E402
    observe_market_v2,
    select_market_v2,
)
from services.options.fyers_native_option_chain_engine_v2 import (  # noqa: E402
    FyersNativeOptionChainEngineV2,
)
from services.options.fyers_option_chain_provider_v2 import FyersOptionChainProviderV2  # noqa: E402


def _load_environment(path_text: str) -> bool:
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        print("ENV FILE NOT FOUND")
        return False
    load_dotenv(dotenv_path=path, override=False)
    return True


def _load_instruments(path_text: str):
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError("ANGEL_INSTRUMENT_MASTER_NOT_FOUND")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise RuntimeError("ANGEL_INSTRUMENT_MASTER_INVALID")
    return rows


def _install_ipv4_filter():
    original = socket.getaddrinfo

    def filtered(host, port, family=0, type=0, proto=0, flags=0):
        if isinstance(host, str) and host.endswith("fyers.in"):
            family = socket.AF_INET
        return original(host, port, family, type, proto, flags)

    socket.getaddrinfo = filtered

    def restore():
        if socket.getaddrinfo is filtered:
            socket.getaddrinfo = original

    return restore


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _resolve_angel_index_identity(rows, market):
    market = market.upper()
    exchange = "NSE" if market == "NIFTY" else "BSE"
    aliases = {
        "NIFTY": {"NIFTY", "NIFTY 50"},
        "SENSEX": {"SENSEX", "BSE SENSEX", "S&P BSE SENSEX"},
    }[market]
    index_types = {"AMXIDX", "INDEX", "IDX", "INDICES", "INDEXSPOT"}
    exact = []
    fallback = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _norm(row.get("exch_seg") or row.get("exchange")) != exchange:
            continue
        token = str(
            row.get("token")
            or row.get("symboltoken")
            or row.get("symbolToken")
            or ""
        ).strip()
        if not token:
            continue
        texts = {
            _norm(row.get("symbol")),
            _norm(row.get("name")),
            _norm(row.get("tradingsymbol") or row.get("tradingSymbol")),
        }
        if not texts.intersection(aliases):
            continue
        instrument_type = _norm(row.get("instrumenttype") or row.get("instrument_type"))
        if instrument_type in index_types:
            exact.append((row, token))
        else:
            expiry = str(row.get("expiry") or "").strip()
            strike = str(row.get("strike") or "").strip()
            if not expiry and strike in {"", "0", "0.0", "-1", "-1.0"}:
                fallback.append((row, token))
    candidates = exact or fallback
    unique = {(exchange, token): row for row, token in candidates}
    if len(unique) != 1:
        raise RuntimeError(f"ANGEL_{market}_INDEX_IDENTITY_AMBIGUOUS:{len(unique)}")
    (exchange, token), row = next(iter(unique.items()))
    trading = str(
        row.get("tradingsymbol")
        or row.get("tradingSymbol")
        or row.get("symbol")
        or row.get("name")
        or market
    ).strip()
    return AngelShadowIdentityV2(
        market_symbol=market,
        exchange=exchange,
        tradingsymbol=trading,
        symboltoken=token,
    )


def _missing_credentials():
    required = []
    if not os.getenv("FYERS_APP_ID"):
        required.append("FYERS_APP_ID")
    if not os.getenv("FYERS_ACCESS_TOKEN"):
        required.append("FYERS_ACCESS_TOKEN")
    if not os.getenv("ANGEL_API_KEY"):
        required.append("ANGEL_API_KEY")
    if not (os.getenv("ANGEL_CLIENT_ID") or os.getenv("ANGEL_USER_ID")):
        required.append("ANGEL_CLIENT_ID_OR_USER_ID")
    if not (os.getenv("ANGEL_PIN") or os.getenv("ANGEL_PASSWORD")):
        required.append("ANGEL_PIN_OR_PASSWORD")
    if not os.getenv("ANGEL_TOTP_SECRET"):
        required.append("ANGEL_TOTP_SECRET")
    return tuple(required)


def _load_angel_market_data_client_class():
    """Load Angel client only after the explicit env file is in os.environ."""
    runtime_config = importlib.import_module("config")
    importlib.reload(runtime_config)
    angel_client_module = importlib.import_module("services.broker.angel_client")
    angel_client_module = importlib.reload(angel_client_module)
    return angel_client_module.AngelMarketDataClient


def _premarket_summary(bot):
    value = getattr(bot, "_last_premarket_state", None)
    if value is None:
        return {"available": False}
    try:
        payload = asdict(value) if is_dataclass(value) else value
        return {
            "available": True,
            "previous_session_status": getattr(value, "previous_session_status", None),
            "global": getattr(getattr(value, "global_risk", None), "evidence_status", None),
            "vix": getattr(getattr(value, "volatility", None), "evidence_status", None),
            "flow": getattr(getattr(value, "institutional_flow", None), "evidence_status", None),
            "event": getattr(getattr(value, "event_risk", None), "evidence_status", None),
            "payload_type": type(payload).__name__,
        }
    except Exception:
        return {"available": True, "summary_error": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--instruments", required=True)
    parser.add_argument("--ipv4-only", action="store_true")
    parser.add_argument("--max-ltp-bps", type=float, default=100.0)
    args = parser.parse_args()

    if not _load_environment(args.env_file):
        return 2
    missing = _missing_credentials()
    if missing:
        print("MISSING CREDENTIAL GROUPS =", ",".join(missing))
        return 2

    # angel_client imports credential constants from config at module import
    # time. Import/reload it only after the explicit env file is loaded.
    AngelMarketDataClient = _load_angel_market_data_client_class()

    rows = _load_instruments(args.instruments)
    rest_log = tempfile.mkdtemp(prefix="ai_trading_copilot_f14_rest_")
    stream_log = tempfile.mkdtemp(prefix="ai_trading_copilot_f14_stream_")
    restore_dns = _install_ipv4_filter() if args.ipv4_only else None
    streaming = None
    bots = []
    success = False

    try:
        fyers_client = build_fyers_data_client_v2(
            client_id=os.environ["FYERS_APP_ID"],
            access_token=os.environ["FYERS_ACCESS_TOKEN"],
            log_path=rest_log,
        )
        streaming = FyersStreamingDataProviderV2(
            client_id=os.environ["FYERS_APP_ID"],
            access_token=os.environ["FYERS_ACCESS_TOKEN"],
            log_path=stream_log,
            reconnect=True,
            ipv4_only=args.ipv4_only,
        )
        runtime = build_fyers_provider_runtime_v2(
            data_client=fyers_client,
            streaming=streaming,
        )
        legacy_identity = FyersLegacyIdentityResolverV2(
            instrument_rows=rows,
            resolver=runtime.resolver,
        )
        compatibility = FyersDataOnlyCompatibilityV2(
            client=fyers_client,
            symbol_resolver=legacy_identity,
        )
        native_provider = FyersOptionChainProviderV2(fyers_client)

        angel_shadow = AngelShadowDataProviderV2(AngelMarketDataClient())
        parity = ProviderShadowParityEngineV2(
            ShadowParityThresholdsV2(quote_ltp_bps=args.max_ltp_bps)
        )

        print("F14 TWO-MARKET OBSERVATIONAL CANARY")
        print("as_of =", datetime.now(timezone.utc).isoformat())
        print("angel_registry_status =", get_provider_registration("ANGEL_SMARTAPI").adapter_status)
        print("automatic_fallback =", automatic_fallback_provider("NIFTY", "QUOTE"))

        observations = {}
        parity_reports = {}
        market_gates = []

        for market in ("NIFTY", "SENSEX"):
            native_engine = FyersNativeOptionChainEngineV2(
                market=market,
                provider=native_provider,
                resolver=runtime.resolver,
                legacy_identity_resolver=legacy_identity,
                cache_ttl=60,
                native_strike_count=10,
            )
            bot = ProviderInjectedUnifiedTradingBotV2(
                market,
                provider_runtime=runtime,
                legacy_data_api=compatibility,
                native_option_chain_engine=native_engine,
            )
            bots.append(bot)
            result = observe_market_v2(bot)
            observations[market] = result

            primary_instrument = runtime.resolver.resolve(
                market_symbol=market,
                instrument_type="UNDERLYING",
                as_of=datetime.now(timezone.utc),
            )
            primary_quote = runtime.quote_depth.get_quote(primary_instrument)
            shadow_identity = _resolve_angel_index_identity(rows, market)
            shadow_quote = angel_shadow.get_quote(shadow_identity)
            report = parity.compare_quote(market, primary_quote, shadow_quote)
            parity_reports[market] = report

            pm = _premarket_summary(bot)
            candidate = result.diagnostic_candidate or {}
            quote = result.executable_quote or {}
            targets = result.targets or {}

            print()
            print(
                market,
                "spot=", result.spot,
                "expiry=", result.expiry,
                "options=", result.option_count,
                "chain_status=", result.chain_status,
                "chain_reason=", result.chain_reason,
                "pcr_oi=", result.pcr_oi,
            )
            print(
                market,
                "mtf=", result.mtf_consensus,
                "regime=", result.regime,
                "bias=", result.prediction.get("bias"),
                "readiness=", result.prediction.get("readiness"),
                "action=", result.prediction.get("action"),
                "blockers=", result.prediction.get("blockers"),
            )
            print(market, "premarket=", pm)
            print(
                market,
                "candidate=", candidate.get("type"), candidate.get("strike"),
                "score=", candidate.get("score"),
                "bid=", quote.get("bid"),
                "ask=", quote.get("ask"),
                "paper_fill=", result.paper_fill,
                "lot_size=", result.lot_size,
                "lots_affordable=", result.lots_affordable,
                "targets=", targets,
            )
            print(
                market,
                "ws=", result.websocket_status,
                "counters_unchanged=", result.counters_unchanged,
                "prediction_disk_write=", result.prediction.get("persisted_to_disk"),
                "shadow_parity=", report.status,
                "shadow_complete=", report.evidence_complete,
            )

            safe_chain = (
                result.chain_status == "OK"
                or (
                    result.chain_status == "EVIDENCE_UNAVAILABLE"
                    and result.chain_reason == "NATIVE_EXPIRY_IDENTITY_MISMATCH"
                    and result.option_count == 0
                )
            )
            market_gates.append(
                result.connected
                and result.spot > 0
                and result.chain_request_count == 1
                and result.chain_depth_fanout == 0
                and safe_chain
                and result.websocket_healthy
                and result.counters_unchanged
                and result.prediction.get("persisted_to_disk") is False
                and result.premarket_available
                and report.evidence_complete
                and report.status == "MATCH"
            )
            bot.close_provider_subscription()

        selection = select_market_v2(observations["NIFTY"], observations["SENSEX"])
        print()
        print(
            "market_selection=", selection.get("selection"),
            "nifty_score=", selection.get("nifty_score"),
            "sensex_score=", selection.get("sensex_score"),
            "reason=", selection.get("reason"),
        )

        candidate_results = [
            result for result in observations.values()
            if result.diagnostic_candidate is not None
        ]
        execution_proven = any(
            result.executable_quote is not None
            and result.paper_fill is not None
            and result.lot_size is not None
            and result.targets is not None
            for result in candidate_results
        )

        success = (
            len(market_gates) == 2
            and all(market_gates)
            and execution_proven
            and selection.get("selection")
            in {"SELECT_NIFTY", "SELECT_SENSEX", "DUAL_WATCH"}
            and get_provider_registration("ANGEL_SMARTAPI").adapter_status
            == "PENDING_V2_ADAPTER"
            and automatic_fallback_provider("NIFTY", "QUOTE") is None
        )
    finally:
        for bot in bots:
            try:
                bot.close_provider_subscription()
            except Exception:
                pass
        if streaming is not None:
            try:
                streaming.close()
            except Exception:
                pass
        if restore_dns is not None:
            restore_dns()
        shutil.rmtree(rest_log, ignore_errors=True)
        shutil.rmtree(stream_log, ignore_errors=True)

    print()
    print("OBSERVATION_ONLY=True")
    print("PREDICTION_LEDGER_WRITES=0")
    print("PAPER_COUNTER_MUTATIONS=0")
    print("FYERS_PRIMARY=True")
    print("ANGEL_SHADOW_ONLY=True")
    print("AUTOMATIC_FALLBACK_ALLOWED=False")
    print("ORDER_API_EXECUTED=False")
    print("ORDER_SOCKET_CREATED=False")
    print("PAPER_CERTIFICATION_STARTED=False")
    print("P8D0_F14_TWO_MARKET_CANARY=", "PASS" if success else "HOLD")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

"""F13 bounded native FYERS option-chain proof.

Read-only. Proves one native option-chain request, zero per-contract depth
fanout, exact legacy identity projection and fail-closed behavior when FYERS
has not yet rolled its default expiry. It never calls run_single_session(),
loads/saves PAPER state, or uses any order API/socket.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from provider_injected_target_bot_v2 import ProviderInjectedUnifiedTradingBotV2  # noqa: E402
from services.broker.fyers_data_compatibility_v2 import FyersDataOnlyCompatibilityV2  # noqa: E402
from services.broker.fyers_legacy_identity_resolver_v2 import FyersLegacyIdentityResolverV2  # noqa: E402
from services.broker.fyers_provider_runtime_v2 import build_fyers_provider_runtime_v2  # noqa: E402
from services.broker.fyers_sdk_data_client_v2 import build_fyers_data_client_v2  # noqa: E402
from services.broker.fyers_streaming_v2 import FyersStreamingDataProviderV2  # noqa: E402
from services.options.fyers_native_option_chain_engine_v2 import FyersNativeOptionChainEngineV2  # noqa: E402
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--instruments", required=True)
    parser.add_argument("--ipv4-only", action="store_true")
    parser.add_argument("--strike-count", type=int, default=10)
    args = parser.parse_args()

    if not _load_environment(args.env_file):
        return 2

    app_id = os.getenv("FYERS_APP_ID")
    token = os.getenv("FYERS_ACCESS_TOKEN")
    if not app_id or not token:
        print("MISSING CREDENTIALS: FYERS_APP_ID / FYERS_ACCESS_TOKEN")
        return 2

    rows = _load_instruments(args.instruments)
    rest_log = tempfile.mkdtemp(prefix="ai_trading_copilot_f13_rest_")
    stream_log = tempfile.mkdtemp(prefix="ai_trading_copilot_f13_stream_")
    restore_dns = _install_ipv4_filter() if args.ipv4_only else None
    streaming = None
    success = False

    try:
        client = build_fyers_data_client_v2(
            client_id=app_id,
            access_token=token,
            log_path=rest_log,
        )
        streaming = FyersStreamingDataProviderV2(
            client_id=app_id,
            access_token=token,
            log_path=stream_log,
            reconnect=True,
            ipv4_only=args.ipv4_only,
        )
        runtime = build_fyers_provider_runtime_v2(
            data_client=client,
            streaming=streaming,
        )
        legacy_identity = FyersLegacyIdentityResolverV2(
            instrument_rows=rows,
            resolver=runtime.resolver,
        )
        compatibility = FyersDataOnlyCompatibilityV2(
            client=client,
            symbol_resolver=legacy_identity,
        )
        native_provider = FyersOptionChainProviderV2(client)

        print("F13 FYERS NATIVE OPTION-CHAIN PROOF")
        print("as_of =", datetime.now(timezone.utc).isoformat())
        market_results = []

        for market in ("NIFTY", "SENSEX"):
            engine = FyersNativeOptionChainEngineV2(
                market=market,
                provider=native_provider,
                resolver=runtime.resolver,
                legacy_identity_resolver=legacy_identity,
                cache_ttl=60,
                native_strike_count=args.strike_count,
            )
            bot = ProviderInjectedUnifiedTradingBotV2(
                market,
                provider_runtime=runtime,
                legacy_data_api=compatibility,
                native_option_chain_engine=engine,
            )
            before = (bot.current_session, bot.total_trades, bot.certification_counter)
            if not bot.load_instruments():
                print(market, "instrument_load=FAILED")
                market_results.append(False)
                continue

            underlying = runtime.resolver.resolve(
                market_symbol=market,
                instrument_type="UNDERLYING",
                as_of=datetime.now(timezone.utc),
            )
            raw = native_provider.get_option_chain(
                underlying_symbol=underlying["provider_symbol"],
                strike_count=args.strike_count,
            )
            raw_rows = raw.get("rows") or ()

            spot = bot.get_spot()
            expiry = bot.get_expiry()
            options, atm = bot.get_options(spot, expiry) if spot > 0 else ([], 0)
            chain = getattr(bot, "_last_chain", None)
            after = (bot.current_session, bot.total_trades, bot.certification_counter)
            counters_unchanged = before == after == (0, 0, 0)

            status = chain.get("status") if isinstance(chain, dict) else None
            reason = chain.get("reason") if isinstance(chain, dict) else None
            request_count = chain.get("request_count") if isinstance(chain, dict) else None
            depth_fanout = (
                chain.get("per_contract_depth_requests")
                if isinstance(chain, dict)
                else None
            )
            safe_projection = (
                status == "OK"
                and len(options) > 0
                and chain.get("provider") == "FYERS"
            ) if isinstance(chain, dict) else False
            safe_rollover_hold = (
                status == "EVIDENCE_UNAVAILABLE"
                and reason == "NATIVE_EXPIRY_IDENTITY_MISMATCH"
                and len(options) == 0
            )

            print(
                market,
                "spot=", spot,
                "selected_expiry=", expiry,
                "atm=", atm,
                "native_raw_rows=", len(raw_rows),
                "chain_status=", status,
                "chain_reason=", reason,
                "projected_options=", len(options),
                "request_count=", request_count,
                "depth_fanout=", depth_fanout,
                "pcr_oi=", chain.get("pcr_oi") if isinstance(chain, dict) else None,
                "counters_unchanged=", counters_unchanged,
            )

            market_results.append(
                len(raw_rows) > 0
                and raw.get("request_count") == 1
                and raw.get("per_contract_depth_requests") == 0
                and request_count == 1
                and depth_fanout == 0
                and (safe_projection or safe_rollover_hold)
                and counters_unchanged
                and bot.provider_option_chain_status == "READY_NATIVE_FYERS"
                and bot.EXECUTION_MODE == "PAPER"
                and bot.BROKER_SUBMISSION is False
                and bot.LIVE_EXECUTION is False
            )

        success = all(market_results) and len(market_results) == 2
    finally:
        if streaming is not None:
            try:
                streaming.close()
            except Exception:
                pass
        if restore_dns is not None:
            restore_dns()
        shutil.rmtree(rest_log, ignore_errors=True)
        shutil.rmtree(stream_log, ignore_errors=True)

    print("FYERS_NATIVE_OPTION_CHAIN=True")
    print("NATIVE_REQUESTS_PER_FETCH=1")
    print("PER_CONTRACT_DEPTH_FANOUT=0")
    print("FYERS_DATA_ONLY=True")
    print("ORDER_CAPABILITY_ALLOWED=False")
    print("AUTOMATIC_FALLBACK_ALLOWED=False")
    print("LIVE_EXECUTION_ELIGIBLE=False")
    print("ORDER_API_EXECUTED=False")
    print("ORDER_SOCKET_CREATED=False")
    print("PAPER_CERTIFICATION_STARTED=False")
    print("P8D0_F13_LIVE_NATIVE_OPTION_CHAIN=", "PASS" if success else "HOLD")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

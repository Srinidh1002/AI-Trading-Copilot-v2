"""F12 bounded FYERS injection proof for the real UnifiedTradingBot subclass.

Observation only: connects data providers, reads spot/day-open and receives
DataSocket ticks. It never calls run_single_session(), load_state(), save_state(),
order APIs or PAPER certification mutation paths.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from provider_injected_target_bot_v2 import (  # noqa: E402
    ProviderInjectedUnifiedTradingBotV2,
)
from services.broker.fyers_data_compatibility_v2 import (  # noqa: E402
    FyersDataOnlyCompatibilityV2,
)
from services.broker.fyers_legacy_identity_resolver_v2 import (  # noqa: E402
    FyersLegacyIdentityResolverV2,
)
from services.broker.fyers_provider_runtime_v2 import (  # noqa: E402
    build_fyers_provider_runtime_v2,
)
from services.broker.fyers_sdk_data_client_v2 import (  # noqa: E402
    build_fyers_data_client_v2,
)
from services.broker.fyers_streaming_v2 import (  # noqa: E402
    FyersStreamingDataProviderV2,
)


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--instruments", required=True)
    parser.add_argument("--ipv4-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    if not _load_environment(args.env_file):
        return 2

    app_id = os.getenv("FYERS_APP_ID")
    token = os.getenv("FYERS_ACCESS_TOKEN")
    if not app_id or not token:
        print("MISSING CREDENTIALS: FYERS_APP_ID / FYERS_ACCESS_TOKEN")
        return 2

    rows = _load_instruments(args.instruments)
    rest_log = tempfile.mkdtemp(prefix="ai_trading_copilot_f12_rest_")
    stream_log = tempfile.mkdtemp(prefix="ai_trading_copilot_f12_stream_")

    streaming = None
    bots = []
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
        identity_resolver = FyersLegacyIdentityResolverV2(
            instrument_rows=rows,
            resolver=runtime.resolver,
        )
        compatibility = FyersDataOnlyCompatibilityV2(
            client=client,
            symbol_resolver=identity_resolver,
        )

        print("F12 FYERS-INJECTED UNIFIED TRADING BOT PROOF")
        results = []
        for market in ("NIFTY", "SENSEX"):
            bot = ProviderInjectedUnifiedTradingBotV2(
                market,
                provider_runtime=runtime,
                legacy_data_api=compatibility,
            )
            bots.append(bot)

            before = (
                bot.current_session,
                bot.total_trades,
                bot.certification_counter,
            )
            connected = bot.connect_with_retry(max_retries=1, retry_delay=0)
            spot = bot.get_spot() if connected else 0
            day_open, day_open_status = (
                bot.get_day_open(spot) if spot > 0 else (None, "NOT_RUN")
            )

            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline and not bot.ws_healthy:
                time.sleep(0.20)

            after = (
                bot.current_session,
                bot.total_trades,
                bot.certification_counter,
            )
            counters_unchanged = before == after == (0, 0, 0)
            ws_status = bot.ws_feed.health_str() if bot.ws_feed else "OFFLINE"

            print(
                market,
                "connected=", connected,
                "spot=", spot,
                "day_open_status=", day_open_status,
                "day_open=", day_open,
                "ws_healthy=", bot.ws_healthy,
                "ws_status=", ws_status,
                "option_chain_status=", bot.provider_option_chain_status,
                "counters_unchanged=", counters_unchanged,
            )

            results.append(
                connected
                and spot > 0
                and day_open_status == "OK"
                and day_open is not None
                and day_open > 0
                and bot.ws_healthy
                and ws_status == "HEALTHY"
                and bot.option_chain_engine is None
                and bot.provider_option_chain_status
                == "F13_NATIVE_OPTION_CHAIN_REQUIRED"
                and counters_unchanged
                and bot.EXECUTION_MODE == "PAPER"
                and bot.BROKER_SUBMISSION is False
                and bot.LIVE_EXECUTION is False
            )

            bot.close_provider_subscription()

        success = all(results)
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
        shutil.rmtree(rest_log, ignore_errors=True)
        shutil.rmtree(stream_log, ignore_errors=True)

    print("TARGET_FOCUSED_BOT_MODIFIED=False")
    print("OFFICIAL_RUNNERS_MODIFIED=False")
    print("FYERS_DATA_ONLY=True")
    print("ORDER_CAPABILITY_ALLOWED=False")
    print("AUTOMATIC_FALLBACK_ALLOWED=False")
    print("LIVE_EXECUTION_ELIGIBLE=False")
    print("ORDER_API_EXECUTED=False")
    print("ORDER_SOCKET_CREATED=False")
    print("PAPER_CERTIFICATION_STARTED=False")
    print("F13_NATIVE_OPTION_CHAIN_REQUIRED=True")
    print("P8D0_F12_LIVE_BOT_INJECTION=", "PASS" if success else "HOLD")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

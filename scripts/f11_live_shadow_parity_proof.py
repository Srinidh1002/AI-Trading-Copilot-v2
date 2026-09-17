"""F11 bounded FYERS PRIMARY vs Angel SHADOW quote parity proof.

Read-only. No order API/socket. No fallback. No PAPER certification mutation.
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


def _load_environment(path_text: str) -> bool:
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        print("ENV FILE NOT FOUND")
        return False
    load_dotenv(dotenv_path=path, override=False)
    return True


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
    from services.broker.provider_shadow_parity_v2 import AngelShadowIdentityV2

    market = market.upper()
    expected_exchange = "NSE" if market == "NIFTY" else "BSE"
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
        exchange = _norm(row.get("exch_seg") or row.get("exchange"))
        if exchange != expected_exchange:
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
        if not (texts & aliases):
            continue
        instrument_type = _norm(
            row.get("instrumenttype") or row.get("instrument_type")
        )
        candidate = (row, token)
        if instrument_type in index_types:
            exact.append(candidate)
        else:
            expiry = str(row.get("expiry") or "").strip()
            strike = str(row.get("strike") or "").strip()
            if not expiry and strike in {"", "0", "0.0", "-1", "-1.0"}:
                fallback.append(candidate)

    candidates = exact or fallback
    unique = {}
    for row, token in candidates:
        unique[(expected_exchange, token)] = row
    if len(unique) != 1:
        raise RuntimeError(
            f"ANGEL_{market}_INDEX_IDENTITY_AMBIGUOUS count={len(unique)}"
        )
    (exchange, token), row = next(iter(unique.items()))
    trading_symbol = str(
        row.get("tradingsymbol")
        or row.get("tradingSymbol")
        or row.get("symbol")
        or row.get("name")
        or market
    ).strip()
    return AngelShadowIdentityV2(
        market_symbol=market,
        exchange=exchange,
        tradingsymbol=trading_symbol,
        symboltoken=token,
    )


def _missing_credential_groups() -> tuple[str, ...]:
    missing = []
    if not os.getenv("FYERS_APP_ID"):
        missing.append("FYERS_APP_ID")
    if not os.getenv("FYERS_ACCESS_TOKEN"):
        missing.append("FYERS_ACCESS_TOKEN")
    if not os.getenv("ANGEL_API_KEY"):
        missing.append("ANGEL_API_KEY")
    if not (os.getenv("ANGEL_CLIENT_ID") or os.getenv("ANGEL_USER_ID")):
        missing.append("ANGEL_CLIENT_ID_OR_USER_ID")
    if not (os.getenv("ANGEL_PIN") or os.getenv("ANGEL_PASSWORD")):
        missing.append("ANGEL_PIN_OR_PASSWORD")
    if not os.getenv("ANGEL_TOTP_SECRET"):
        missing.append("ANGEL_TOTP_SECRET")
    return tuple(missing)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--instruments", default="data/instruments.json")
    parser.add_argument("--ipv4-only", action="store_true")
    parser.add_argument("--max-ltp-bps", type=float, default=100.0)
    args = parser.parse_args()

    if not _load_environment(args.env_file):
        return 2

    missing = _missing_credential_groups()
    if missing:
        print("MISSING CREDENTIAL GROUPS =", ",".join(missing))
        return 2

    instrument_path = Path(args.instruments)
    if not instrument_path.is_file():
        print("ANGEL INSTRUMENT MASTER NOT FOUND")
        return 2
    rows = json.loads(instrument_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        print("ANGEL INSTRUMENT MASTER INVALID")
        return 2

    from services.broker.angel_client import AngelMarketDataClient
    from services.broker.angel_shadow_data_v2 import AngelShadowDataProviderV2
    from services.broker.fyers_five_market_resolver_v2 import (
        FyersFiveMarketInstrumentResolverV2,
    )
    from services.broker.fyers_provider_adapters_v2 import FyersQuoteDepthProviderV2
    from services.broker.fyers_sdk_data_client_v2 import build_fyers_data_client_v2
    from services.broker.provider_registry_v2 import get_provider_registration
    from services.broker.provider_shadow_parity_v2 import (
        ProviderShadowParityEngineV2,
        ShadowParityThresholdsV2,
    )
    from services.core.provider_routing_policy_v2 import automatic_fallback_provider

    fyers_log_dir = tempfile.mkdtemp(prefix="ai_trading_copilot_f11_fyers_")
    restore_dns = _install_ipv4_filter() if args.ipv4_only else None
    success = False
    try:
        fyers_client = build_fyers_data_client_v2(
            client_id=os.environ["FYERS_APP_ID"],
            access_token=os.environ["FYERS_ACCESS_TOKEN"],
            log_path=fyers_log_dir,
        )
        fyers_resolver = FyersFiveMarketInstrumentResolverV2(data_client=fyers_client)
        fyers_quotes = FyersQuoteDepthProviderV2(fyers_client)

        angel_client = AngelMarketDataClient()
        angel_shadow = AngelShadowDataProviderV2(angel_client)
        parity = ProviderShadowParityEngineV2(
            ShadowParityThresholdsV2(quote_ltp_bps=args.max_ltp_bps)
        )

        print("F11 FYERS PRIMARY / ANGEL SHADOW PARITY PROOF")
        print(
            "angel_registry_status =",
            get_provider_registration("ANGEL_SMARTAPI").adapter_status,
        )
        print(
            "automatic_fallback =",
            automatic_fallback_provider("NIFTY", "QUOTE"),
        )

        results = []
        as_of = datetime.now(timezone.utc)
        for market in ("NIFTY", "SENSEX"):
            primary_instrument = fyers_resolver.resolve(
                market_symbol=market,
                instrument_type="UNDERLYING",
                as_of=as_of,
            )
            primary_quote = fyers_quotes.get_quote(primary_instrument)
            shadow_identity = _resolve_angel_index_identity(rows, market)
            shadow_quote = angel_shadow.get_quote(shadow_identity)
            report = parity.compare_quote(market, primary_quote, shadow_quote)
            ltp_metric = next(
                metric for metric in report.metrics if metric.field == "last_price"
            )
            print(
                market,
                "fyers_ltp=",
                primary_quote["last_price"],
                "angel_ltp=",
                shadow_quote["last_price"],
                "ltp_divergence_bps=",
                round(ltp_metric.divergence or 0.0, 4),
                "status=",
                report.status,
                "complete=",
                report.evidence_complete,
            )
            results.append(report)

        success = (
            get_provider_registration("ANGEL_SMARTAPI").adapter_status
            == "PENDING_V2_ADAPTER"
            and automatic_fallback_provider("NIFTY", "QUOTE") is None
            and all(
                report.evidence_complete and report.status == "MATCH"
                for report in results
            )
        )
    finally:
        if restore_dns is not None:
            restore_dns()
        shutil.rmtree(fyers_log_dir, ignore_errors=True)

    print("FYERS_PRIMARY=True")
    print("ANGEL_SHADOW_ONLY=True")
    print("ANGEL_ADAPTER_READY=False")
    print("AUTOMATIC_FALLBACK_ALLOWED=False")
    print("ORDER_API_EXECUTED=False")
    print("ORDER_SOCKET_CREATED=False")
    print("PAPER_CERTIFICATION_STARTED=False")
    print("P8D0_F11_LIVE_SHADOW_PARITY=", "PASS" if success else "HOLD")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

"""F8 - bounded read-only live FYERS proof. DATA ONLY.

No order APIs. No order sockets. No PAPER certification. Sanitized output.

Requires FYERS_APP_ID and FYERS_ACCESS_TOKEN in .env (loaded through the
F7 credential boundary). Never prints tokens.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from services.broker.fyers_sdk_data_client_v2 import build_fyers_data_client_v2
from services.broker.fyers_five_market_resolver_v2 import (
    FyersFiveMarketInstrumentResolverV2,
)


def _safe_print(label, value):
    print(f"  {label:<28} = {value}")


def main() -> int:
    load_dotenv()
    app_id = os.getenv("FYERS_APP_ID") or os.getenv("ANGEL_API_KEY")
    token = os.getenv("FYERS_ACCESS_TOKEN")
    if not app_id or not token:
        print("MISSING CREDENTIALS: set FYERS_APP_ID and FYERS_ACCESS_TOKEN")
        return 2

    # FyersModel appends "fyersApi.log" to log_path via os.path.join,
    # so log_path must be a directory that already exists.
    log_dir = "logs/f8_fyers_client"
    os.makedirs(log_dir, exist_ok=True)
    client = build_fyers_data_client_v2(
        client_id=app_id,
        access_token=token,
        log_path=log_dir,
    )

    # NOTE: master_store must be populated before running the live proof.
    # The operator is expected to have downloaded FYERS public symbol
    # masters (BSE_CM / BSE_FO / MCX_COM) into
    # data/provider_cache/fyers_master/{segment}.json via the F7 boundary.
    resolver = FyersFiveMarketInstrumentResolverV2(data_client=client)
    as_of = datetime.now(timezone.utc)

    print("F8 LIVE READ-ONLY PROOF (sanitized)")
    print("as_of:", as_of.isoformat())
    print()

    # Underlyings
    for ms in ("NIFTY", "SENSEX"):
        r = resolver.resolve(
            market_symbol=ms, instrument_type="UNDERLYING", as_of=as_of,
        )
        _safe_print(ms + " underlying", r["provider_symbol"])
        _safe_print("  exchange", r["provider_exchange"])
        _safe_print("  data_only", r["data_only"])

    # NIFTY futures via native futures_chain
    try:
        r = resolver.resolve(
            market_symbol="NIFTY", instrument_type="FUTURE", as_of=as_of,
        )
        _safe_print("NIFTY front FUT", r["provider_symbol"])
        _safe_print("  expiry", r["expiry"])
    except Exception as e:
        print("  NIFTY FUT error:", type(e).__name__, str(e)[:80])

    # SENSEX futures
    try:
        r = resolver.resolve(
            market_symbol="SENSEX", instrument_type="FUTURE", as_of=as_of,
        )
        _safe_print("SENSEX front FUT", r["provider_symbol"])
        _safe_print("  expiry", r["expiry"])
    except Exception as e:
        print("  SENSEX FUT error:", type(e).__name__, str(e)[:80])

    # MCX front futures
    for ms in ("CRUDEOILM", "GOLDM", "NATGASMINI"):
        try:
            r = resolver.resolve(
                market_symbol=ms, instrument_type="FUTURE", as_of=as_of,
            )
            _safe_print(ms + " front FUT", r["provider_symbol"])
            _safe_print("  expiry", r["expiry"])
        except Exception as e:
            print(f"  {ms} FUT error:", type(e).__name__, str(e)[:80])

    # NIFTY / SENSEX options: pick a real (expiry, strike) pair from
    # the master, then resolve via the production path.
    from services.broker.fyers_symbol_master_v2 import FyersSymbolMasterStoreV2

    store = FyersSymbolMasterStoreV2()
    for market, seg_name in (("NIFTY", "NSE_FO"), ("SENSEX", "BSE_FO")):
        try:
            idx = store.get_index(seg_name)
        except Exception as e:
            print(f"  {market} option error: master unavailable "
                  f"({type(e).__name__})")
            continue
        opts = [
            r for r in idx.records
            if r.instrument_kind == "OPTION"
            and (r.underlying_symbol or "").upper() == market
            and r.expiry is not None
            and r.expiry > as_of.date()
            and r.strike is not None
            and r.strike > 0
            and r.option_type in ("CE", "PE")
        ]
        if not opts:
            print(f"  {market} option error: no non-expired options in master")
            continue
        nearest = min(r.expiry for r in opts)
        at_nearest = [r for r in opts if r.expiry == nearest]
        strikes = sorted({r.strike for r in at_nearest})
        # pick median strike (or the only one)
        pick = strikes[len(strikes) // 2]
        for ot in ("CE", "PE"):
            try:
                r = resolver.resolve(
                    market_symbol=market, instrument_type="OPTION",
                    as_of=as_of, expiry=nearest,
                    strike=float(pick), option_type=ot,
                )
                _safe_print(f"{market} {ot} @ {nearest} {pick}",
                            r["provider_symbol"])
            except Exception as e:
                print(f"  {market} {ot} error: {type(e).__name__}: {str(e)[:80]}")

    print()
    print("ORDER_API_EXECUTED=False")
    print("ORDER_SOCKET_CREATED=False")
    print("PAPER_CERTIFICATION_STARTED=False")
    return 0


if __name__ == "__main__":
    from datetime import date  # noqa: F401 (used above)
    sys.exit(main())

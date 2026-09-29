"""FYERS authenticated DataSocket live canary — F15-R2 Phase R2-12.

Read-only proof that FYERS API v3 WebSocket works with the current
access token, ahead of the 2026-09-30 FYERS WebSocket auth requirement.

Data-only. No order socket. No state writes. Never prints token values.

Exit codes:
    0  all subscribed markets connected and subscribed
    1  one or more markets failed to connect
    2  configuration / credential error
    3  SDK import error

Per-market output fields:
    <MARKET>_CONNECT          PASS | FAIL | SKIP
    <MARKET>_SUBSCRIPTION     PASS | FAIL | SKIP
    <MARKET>_MESSAGE_RECEIVED True | False
    <MARKET>_MESSAGE_SYMBOL   provider symbol from first live tick (if any)

A closed market may connect and subscribe but emit no tick. That is
reported as MESSAGE_RECEIVED=False with CONNECT=PASS, not as auth
failure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))


def _install_ipv4_only_filter():
    """Force socket.getaddrinfo to return IPv4 only.

    Mirrors services/broker/fyers_streaming_v2._install_fyers_ipv4_filter.
    The FYERS SDK WebSocket occasionally tries an IPv6 address first and
    times out (WinError 10060).
    """
    import socket as _sock
    original = _sock.getaddrinfo

    def filtered(host, port, family=0, type=0, proto=0, flags=0):
        return original(host, port, _sock.AF_INET, type, proto, flags)

    _sock.getaddrinfo = filtered
    return lambda: setattr(_sock, "getaddrinfo", original)


def _load_env(env_file):
    try:
        from dotenv import load_dotenv
        load_dotenv(str(env_file), override=False)
    except Exception:
        pass


def _qualified_token(access_token, client_id):
    token = str(access_token or "").strip()
    if not token:
        raise ValueError("access_token empty")
    if ":" in token:
        return token
    cid = str(client_id or "").strip()
    if not cid:
        raise ValueError("client_id required for unqualified token")
    return f"{cid}:{token}"


def _resolve_mcx_future(log_dir, product="CRUDEOILM"):
    try:
        from mcx.mcx_fyers_runtime_v2 import build_mcx_fyers_runtime_from_env_v2
        runtime = build_mcx_fyers_runtime_from_env_v2(log_path=str(log_dir))
        if runtime is None:
            return None
        res = runtime.identity.resolve_active(product)
        if not isinstance(res, dict) or res.get("status") != "OK":
            return None
        fut = res.get("futures") or {}
        sym = str(fut.get("symbol") or "").strip()
        return sym or None
    except Exception:
        return None


class _Capture:
    def __init__(self):
        self.messages = []
        self.errors = []
        self.connected = threading.Event()
        self.lock = threading.Lock()

    def on_connect(self):
        self.connected.set()

    def on_close(self, message=None):
        del message

    def on_error(self, message):
        with self.lock:
            if len(self.errors) < 10:
                self.errors.append(str(message)[:200] if message else "unknown")

    def on_message(self, message):
        with self.lock:
            if len(self.messages) < 50:
                payload = message if isinstance(message, dict) else {"raw": str(message)[:200]}
                self.messages.append({
                    "received_at_utc": datetime.now(UTC).isoformat(),
                    "payload": payload,
                })


def _extract_symbol(payload):
    if not isinstance(payload, dict):
        return None
    for k in ("symbol", "provider_symbol"):
        v = payload.get(k)
        if v:
            return str(v)
    inner = payload.get("data")
    if isinstance(inner, dict):
        v = inner.get("symbol")
        if v:
            return str(v)
    return None


def _run_market(factory, qualified, log_dir, symbols, timeout_seconds, label):
    cap = _Capture()
    result = {
        "connect": "FAIL",
        "subscribe": "FAIL",
        "message_received": False,
        "first_message_symbol": None,
        "errors": [],
    }
    try:
        socket = factory(
            access_token=qualified,
            log_path=str(log_dir),
            litemode=False,
            write_to_file=False,
            reconnect=False,
            on_connect=cap.on_connect,
            on_close=cap.on_close,
            on_error=cap.on_error,
            on_message=cap.on_message,
        )
    except Exception as e:
        result["errors"].append(f"construct:{type(e).__name__}")
        return result

    reader = threading.Thread(target=socket.connect, name=f"canary-{label}", daemon=True)
    reader.start()

    if not cap.connected.wait(timeout=10.0):
        try:
            socket.close_connection()
        except Exception:
            pass
        result["errors"].append("connect_timeout")
        return result

    result["connect"] = "PASS"

    try:
        socket.subscribe(symbols=symbols, data_type="SymbolUpdate")
    except Exception as e:
        result["errors"].append(f"subscribe:{type(e).__name__}")
        try:
            socket.close_connection()
        except Exception:
            pass
        return result

    result["subscribe"] = "PASS"

    deadline = time.monotonic() + float(timeout_seconds)
    while time.monotonic() < deadline:
        with cap.lock:
            if cap.messages:
                break
        time.sleep(0.2)

    with cap.lock:
        first = cap.messages[0] if cap.messages else None
        errs = list(cap.errors)

    result["errors"] = errs
    if first:
        result["message_received"] = True
        result["first_message_symbol"] = _extract_symbol(first["payload"])

    try:
        socket.unsubscribe(symbols=symbols, data_type="SymbolUpdate")
    except Exception:
        pass
    try:
        socket.close_connection()
    except Exception:
        pass

    return result


def _market_session_open(label):
    """Best-effort market hours check (IST). Not a calendar authority,
    only used to decide whether a missing tick is a failure."""
    from datetime import datetime as _dt
    from datetime import timedelta as _td
    from datetime import timezone as _tz
    ist = _dt.now(_tz(_td(hours=5, minutes=30)))
    if ist.weekday() >= 5:
        return False
    mins = ist.hour * 60 + ist.minute
    if label in ("NIFTY", "SENSEX"):
        return 555 <= mins < 930          # 09:15 - 15:30
    if label == "MCX":
        return 540 <= mins < 1410          # 09:00 - 23:30
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="FYERS authenticated DataSocket canary (PAPER/data-only)"
    )
    ap.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    ap.add_argument("--log-dir", default=None)
    ap.add_argument("--timeout-seconds", type=float, default=15.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    print("FYERS_WEBSOCKET_AUTH_CANARY_START")
    print(f"ENV_FILE={args.env_file}")
    print("SDK=OFFICIAL_FYERS_V3")
    print("DATA_ONLY=True")
    print("TOKEN_VALUES_PRINTED=False")

    _load_env(args.env_file)

    app_id = os.environ.get("FYERS_APP_ID", "").strip()
    token = os.environ.get("FYERS_ACCESS_TOKEN", "").strip()
    if not token:
        print("FYERS_WEBSOCKET_AUTH_CANARY=FAIL")
        print("REASON=MISSING_TOKEN")
        return 2
    try:
        qualified = _qualified_token(token, app_id)
    except ValueError as e:
        print("FYERS_WEBSOCKET_AUTH_CANARY=FAIL")
        print(f"REASON=TOKEN_CONFIG:{e}")
        return 2

    log_dir = Path(args.log_dir) if args.log_dir else REPO_ROOT / "logs" / "fyers_ws_canary"
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"LOG_DIR={log_dir}")

    try:
        from fyers_apiv3.FyersWebsocket import data_ws
        factory = data_ws.FyersDataSocket
    except Exception as e:
        print("FYERS_WEBSOCKET_AUTH_CANARY=FAIL")
        print(f"REASON=SDK_IMPORT:{type(e).__name__}")
        return 3

    print("FyersDataSocket_available=True")

    _restore_dns = _install_ipv4_only_filter()  # installed for process lifetime

    nifty_sym = "NSE:NIFTY50-INDEX"
    sensex_sym = "BSE:SENSEX-INDEX"
    mcx_sym = _resolve_mcx_future(log_dir, "CRUDEOILM")

    print(f"NIFTY_SYMBOL={nifty_sym}")
    print(f"SENSEX_SYMBOL={sensex_sym}")
    print(f"MCX_SYMBOL={mcx_sym or 'UNRESOLVED'}")

    overall = {"pass": True, "reports": {}}

    for label, symbols in (
        ("NIFTY", [nifty_sym]),
        ("SENSEX", [sensex_sym]),
        ("MCX", [mcx_sym] if mcx_sym else None),
    ):
        print("")
        print(f"--- {label} ---")
        if symbols is None:
            print(f"{label}_CONNECT=SKIP")
            print(f"{label}_SUBSCRIPTION=SKIP")
            print(f"{label}_MESSAGE_RECEIVED=False")
            overall["reports"][label] = {"connect": "SKIP"}
            continue
        r = _run_market(factory, qualified, log_dir, symbols, args.timeout_seconds, label)
        print(f"{label}_CONNECT={r['connect']}")
        print(f"{label}_SUBSCRIPTION={r['subscribe']}")
        print(f"{label}_MESSAGE_RECEIVED={r['message_received']}")
        if r["first_message_symbol"]:
            print(f"{label}_MESSAGE_SYMBOL={r['first_message_symbol']}")
        if r["errors"]:
            print(f"{label}_ERRORS={r['errors']}")
        if r["connect"] != "PASS" or r["subscribe"] != "PASS":
            overall["pass"] = False
        # Market-hours aware message gate. During a live session, no
        # tick on a subscribed symbol is a real failure.
        if label in ("NIFTY", "SENSEX") and _market_session_open(label):
            if not r["message_received"]:
                overall["pass"] = False
        if label == "MCX" and _market_session_open("MCX"):
            if not r["message_received"]:
                overall["pass"] = False
        overall["reports"][label] = r

    print("")
    print(f"FYERS_WEBSOCKET_AUTH_CANARY={'PASS' if overall['pass'] else 'FAIL'}")
    print("TOKEN_VALUES_PRINTED=False")

    if args.json:
        print("")
        print(json.dumps(overall, indent=2, default=str))

    return 0 if overall["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

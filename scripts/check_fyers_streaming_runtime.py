"""F8R2 - FYERS streaming runtime readiness check.

Verifies Python 3.12, FYERS SDK deps, DataSocket import, and performs
one bounded WebSocket handshake (SymbolUpdate on NSE:NIFTY50-INDEX).
No order APIs. No order socket. Sanitized output only.

Usage:
    python scripts/check_fyers_streaming_runtime.py [--ipv4-only]
"""
import argparse
import os
import socket
import sys
import threading
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)


def _install_ipv4_only(host_suffixes):
    """Process-local, host-scoped IPv4-only getaddrinfo patch."""
    orig = socket.getaddrinfo
    def patched(host, port, family=0, type=0, proto=0, flags=0):
        if isinstance(host, str) and any(host.endswith(s) for s in host_suffixes):
            family = socket.AF_INET
        return orig(host, port, family, type, proto, flags)
    socket.getaddrinfo = patched
    def restore():
        socket.getaddrinfo = orig
    return restore


def check_python():
    v = sys.version_info
    print(f"python_version = {v.major}.{v.minor}.{v.micro}")
    return (v.major, v.minor) == (3, 12)


def check_sdk():
    import aiohttp
    import websocket
    print(f"aiohttp = {aiohttp.__version__}")
    print(f"websocket-client = {websocket.__version__}")
    try:
        from importlib.metadata import version
        print(f"fyers-apiv3 = {version('fyers-apiv3')}")
    except Exception:
        print("fyers-apiv3 = (version unknown)")
    return True


def check_imports():
    from fyers_apiv3 import fyersModel  # noqa: F401
    from fyers_apiv3.FyersWebsocket import data_ws  # noqa: F401
    print("FyersModel import = OK")
    print("DataSocket (data_ws) import = OK")
    return True


def bounded_ws_handshake(access_token, ipv4_only=False, timeout=12):
    from fyers_apiv3.FyersWebsocket import data_ws

    state = {"received": 0, "error": None, "connected": False}

    def on_message(msg):
        state["received"] += 1

    def on_error(err):
        state["error"] = type(err).__name__

    def on_close(msg):
        pass

    def on_open():
        state["connected"] = True
        try:
            ws.subscribe(symbols=["NSE:NIFTY50-INDEX"],
                         data_type="SymbolUpdate")
        except Exception as e:
            state["error"] = f"subscribe:{type(e).__name__}"

    restore = None
    if ipv4_only:
        restore = _install_ipv4_only(["fyers.in", "fyersapi"])

    ws = None
    try:
        os.makedirs("logs/f8_ws_probe", exist_ok=True)
        ws = data_ws.FyersDataSocket(
            access_token=access_token,
            log_path="logs/f8_ws_probe",
            litemode=False,
            write_to_file=False,
            reconnect=False,
            on_connect=on_open,
            on_close=on_close,
            on_error=on_error,
            on_message=on_message,
        )
        t = threading.Thread(target=ws.connect, daemon=True)
        t.start()
        t.join(timeout=timeout)
    finally:
        try:
            if ws is not None:
                ws.close_connection()
        except Exception:
            pass
        if restore:
            restore()

    print(f"  ws_connected = {state['connected']}")
    print(f"  ws_messages_received = {state['received']}")
    print(f"  ws_error = {state['error']}")
    return state["connected"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ipv4-only", action="store_true")
    args = ap.parse_args()

    print("F8R2 - streaming runtime readiness")
    print(f"as_of = {datetime.now(timezone.utc).isoformat()}")
    print(f"ipv4_only = {args.ipv4_only}")
    print()

    ok = True
    ok = check_python() and ok
    ok = check_sdk() and ok
    ok = check_imports() and ok

    print()
    print("--- bounded WS handshake ---")
    from dotenv import load_dotenv
    load_dotenv()
    token = os.getenv("FYERS_ACCESS_TOKEN")
    if not token:
        print("MISSING FYERS_ACCESS_TOKEN")
        print()
        print("F9_STREAMING_RUNTIME_READY = False")
        return 1

    ws_ok = bounded_ws_handshake(token, ipv4_only=args.ipv4_only)
    ok = ok and ws_ok

    print()
    print(f"F9_STREAMING_RUNTIME_READY = {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

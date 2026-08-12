"""PAPER-only Task 9 WebSocket collector; no orders and no historical REST."""
from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import ANGEL_API_KEY, ANGEL_CLIENT_ID
from services.broker.shared_client import get_certification_market_client
from services.market.task9_live_tick_stream import (
    Task9LiveTickJournal,
    Task9LiveTickStream,
)


class Task9LiveStreamCollectorLockError(RuntimeError):
    """Exclusive live-stream collector ownership could not be obtained."""


class Task9LiveStreamCollectorLock:
    """Create-only, token-owned process lock; stale locks require operator review."""
    filename = "task9-live-websocket-collector.lock"

    def __init__(self, live_stream_root):
        self.root = Path(live_stream_root)
        self.path = self.root / self.filename
        self._token = uuid.uuid4().hex
        self._owned = False

    def acquire(self):
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"pid": os.getpid(), "acquired_at": datetime.now(timezone.utc).isoformat(), "ownership_token": self._token}
        try:
            with self.path.open("x", encoding="utf-8", newline="") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.flush(); os.fsync(handle.fileno())
        except FileExistsError as exc:
            raise Task9LiveStreamCollectorLockError("TASK9_LIVE_STREAM_COLLECTOR_ALREADY_ACTIVE") from exc
        self._owned = True

    def release(self):
        if not self._owned:
            return
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if value.get("ownership_token") != self._token:
                return
            self.path.unlink()
        finally:
            self._owned = False


def _credentials_from_authenticated_session(client):
    """Extract transient SDK credentials without logging or persisting them."""
    session = client.login()
    data = session.get("data") if type(session) is dict else None
    if type(data) is not dict:
        raise ValueError("authenticated SmartAPI session is unavailable")
    auth_token, feed_token = data.get("jwtToken"), data.get("feedToken")
    if not all(type(value) is str and value for value in (auth_token, feed_token, ANGEL_API_KEY, ANGEL_CLIENT_ID)):
        raise ValueError("authenticated SmartAPI WebSocket credentials are unavailable")
    return {"auth_token": auth_token, "api_key": ANGEL_API_KEY, "client_code": ANGEL_CLIENT_ID, "feed_token": feed_token}


def _official_websocket_factory(**credentials):
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
    # Task9LiveTickStream is the sole reconnect owner; disable SDK recursion.
    return SmartWebSocketV2(**credentials, max_retry_attempt=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Task9 PAPER-only live tick collector")
    parser.add_argument("--persistence-root", default="data/paper_trading/certified_runtime/task9")
    args = parser.parse_args(argv)
    live_stream_root = Path(args.persistence_root) / "live_stream"
    lock = Task9LiveStreamCollectorLock(live_stream_root)
    lock.acquire()
    try:
        client = get_certification_market_client()
        credentials = _credentials_from_authenticated_session(client)
        stream = Task9LiveTickStream(journal=Task9LiveTickJournal(live_stream_root), websocket_factory=_official_websocket_factory, credentials=credentials)
        try:
            stream.run_forever()
        except KeyboardInterrupt:
            stream.request_stop()
    except KeyboardInterrupt:
        pass
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

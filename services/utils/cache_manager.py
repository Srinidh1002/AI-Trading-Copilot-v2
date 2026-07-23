"""
Cache Manager

In-memory cache manager for the
AI Trading Copilot.

Responsibilities
----------------
✓ Store Cached Data
✓ Retrieve Cached Data
✓ Automatic Expiration (TTL)
✓ Remove Cache Entries
✓ Cache Statistics
"""

from __future__ import annotations

import time
from typing import Any


class CacheManager:

    def __init__(self):

        self._cache: dict[str, dict[str, Any]] = {}

    # --------------------------------------------------

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | float | None = None,
    ):

        expiry = None

        if ttl is not None:

            expiry = time.time() + ttl

        self._cache[key] = {

            "value": value,

            "expiry": expiry,

            "created": time.time(),

        }

    # --------------------------------------------------

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        item = self._cache.get(key)

        if item is None:

            return default

        expiry = item["expiry"]

        if expiry is not None and time.time() > expiry:

            self.delete(key)

            return default

        return item["value"]

    # --------------------------------------------------

    def exists(
        self,
        key: str,
    ) -> bool:

        return self.get(key) is not None

    # --------------------------------------------------

    def delete(
        self,
        key: str,
    ) -> bool:

        return self._cache.pop(key, None) is not None

    # --------------------------------------------------

    def clear(self):

        self._cache.clear()

    # --------------------------------------------------

    def cleanup(self):

        now = time.time()

        expired = [

            key

            for key, item in self._cache.items()

            if item["expiry"] is not None
            and now > item["expiry"]

        ]

        for key in expired:

            self.delete(key)

    # --------------------------------------------------

    def keys(self):

        self.cleanup()

        return list(self._cache.keys())

    # --------------------------------------------------

    def values(self):

        self.cleanup()

        return [

            item["value"]

            for item in self._cache.values()

        ]

    # --------------------------------------------------

    def items(self):

        self.cleanup()

        return {

            key: item["value"]

            for key, item in self._cache.items()

        }

    # --------------------------------------------------

    def size(self) -> int:

        self.cleanup()

        return len(self._cache)

    # --------------------------------------------------

    def stats(self):

        self.cleanup()

        now = time.time()

        return {

            "entries": len(self._cache),

            "expired": sum(

                1

                for item in self._cache.values()

                if item["expiry"] is not None
                and now > item["expiry"]

            ),

        }

    # --------------------------------------------------

    def summary(self):

        self.cleanup()

        return {

            "entries": self.size(),

            "keys": self.keys(),

        }
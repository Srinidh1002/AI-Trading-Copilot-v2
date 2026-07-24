"""
Shared Snapshot Cache
"""

import time

from services.refresh.refresh_state import (
    refresh_state,
)

from services.refresh.refresh_intervals import (
    MARKET_SNAPSHOT,
)


class SnapshotCache:

    def get(self, loader):

        now = time.time()

        if (
            refresh_state.market_snapshot is None
            or
            now - refresh_state.last_market_snapshot >= MARKET_SNAPSHOT
        ):

            refresh_state.market_snapshot = loader()

            refresh_state.decision = None

            refresh_state.last_market_snapshot = now

        return refresh_state.market_snapshot

    def invalidate(self):

        refresh_state.market_snapshot = None

        refresh_state.last_market_snapshot = 0


snapshot_cache = SnapshotCache()
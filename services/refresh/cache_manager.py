"""
Global Cache Manager
"""

from services.refresh import (
    snapshot_cache,
    history_cache,
    refresh_state,
)


class CacheManager:

    def clear_all(self):

        snapshot_cache.invalidate()

        history_cache.invalidate()

        refresh_state.market_snapshot = None
        refresh_state.option_chain = None
        refresh_state.greeks = None
        refresh_state.decision = None


cache_manager = CacheManager()
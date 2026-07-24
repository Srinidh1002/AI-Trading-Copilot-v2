"""
Decision History Cache
"""

import time

from services.refresh.refresh_intervals import DATABASE


class HistoryCache:

    def __init__(self):

        self.history = None
        self.last_refresh = 0

    def get(self, loader):

        now = time.time()

        if (
            self.history is None
            or now - self.last_refresh >= DATABASE
        ):

            self.history = loader()
            self.last_refresh = now

        return self.history

    def invalidate(self):

        self.history = None


history_cache = HistoryCache()
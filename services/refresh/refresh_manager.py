"""
Central Refresh Manager
"""

import time


class RefreshManager:

    def __init__(self):

        self.last_refresh = {}

    def should_refresh(
        self,
        name,
        interval,
    ):

        now = time.time()

        previous = self.last_refresh.get(
            name,
            0,
        )

        if now - previous >= interval:

            self.last_refresh[name] = now

            return True

        return False


refresh_manager = RefreshManager()
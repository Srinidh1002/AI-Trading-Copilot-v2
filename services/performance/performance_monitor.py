"""
Performance Monitor
"""

import time


class PerformanceMonitor:

    def __init__(self):

        self.metrics = {}

    def start(self, name):

        self.metrics[name] = {
            "start": time.perf_counter()
        }

    def stop(self, name):

        if name not in self.metrics:
            return

        self.metrics[name]["elapsed"] = round(
            time.perf_counter()
            - self.metrics[name]["start"],
            4,
        )

    def elapsed(self, name):

        return self.metrics.get(
            name,
            {},
        ).get(
            "elapsed",
            0,
        )


performance_monitor = PerformanceMonitor()
"""
Performance Test

Benchmarks the performance of critical AI Trading
Copilot components.

Responsibilities
----------------
✓ Database Performance
✓ Cache Performance
✓ File I/O Performance
✓ Configuration Performance
✓ Memory Usage
✓ Execution Timing
✓ Benchmark Summary
"""

from __future__ import annotations

import time
import tracemalloc
from typing import Any

from services.config.config_manager import ConfigManager
from services.database.database_manager import DatabaseManager
from services.utils.cache_manager import CacheManager
from services.utils.file_manager import FileManager


class PerformanceTest:

    def __init__(self):

        self.results: dict[str, dict[str, Any]] = {}

    # --------------------------------------------------

    def _benchmark(
        self,
        name: str,
        function,
    ):

        tracemalloc.start()

        start = time.perf_counter()

        success = True
        error = None

        try:

            function()

        except Exception as exc:

            success = False
            error = str(exc)

        elapsed = round(

            (time.perf_counter() - start) * 1000,

            3,

        )

        current, peak = tracemalloc.get_traced_memory()

        tracemalloc.stop()

        self.results[name] = {

            "passed": success,

            "time_ms": elapsed,

            "memory_kb": round(

                peak / 1024,

                2,

            ),

            "error": error,

        }

    # --------------------------------------------------

    def database_test(self):

        db = DatabaseManager()

        for _ in range(100):

            db.fetch_one(

                "SELECT 1"

            )

        db.close()

    # --------------------------------------------------

    def cache_test(self):

        cache = CacheManager()

        for i in range(5000):

            cache.set(

                f"key{i}",

                i,

            )

        for i in range(5000):

            cache.get(

                f"key{i}"

            )

    # --------------------------------------------------

    def config_test(self):

        config = ConfigManager()

        for i in range(100):

            config.set(

                f"TEST_{i}",

                i,

            )

            config.get(

                f"TEST_{i}"

            )

    # --------------------------------------------------

    def file_test(self):

        filename = "performance_test.txt"

        FileManager.write_text(

            filename,

            "A" * 10000,

        )

        FileManager.read_text(

            filename,

        )

        FileManager.delete(

            filename,

        )

    # --------------------------------------------------

    def cpu_test(self):

        total = 0

        for i in range(

            500000

        ):

            total += i

        return total

    # --------------------------------------------------

    def run(self):

        self.results.clear()

        self._benchmark(

            "Database",

            self.database_test,

        )

        self._benchmark(

            "Cache",

            self.cache_test,

        )

        self._benchmark(

            "Configuration",

            self.config_test,

        )

        self._benchmark(

            "File Manager",

            self.file_test,

        )

        self._benchmark(

            "CPU",

            self.cpu_test,

        )

        return self.summary()

    # --------------------------------------------------

    def fastest(self):

        return min(

            self.results.items(),

            key=lambda item: item[1]["time_ms"],

        )[0]

    # --------------------------------------------------

    def slowest(self):

        return max(

            self.results.items(),

            key=lambda item: item[1]["time_ms"],

        )[0]

    # --------------------------------------------------

    def average_time(self):

        if not self.results:

            return 0

        return round(

            sum(

                item["time_ms"]

                for item in self.results.values()

            )

            / len(self.results),

            3,

        )

    # --------------------------------------------------

    def summary(self):

        return {

            "benchmarks": len(

                self.results

            ),

            "average_time_ms": self.average_time(),

            "fastest": self.fastest() if self.results else None,

            "slowest": self.slowest() if self.results else None,

            "results": self.results,

        }
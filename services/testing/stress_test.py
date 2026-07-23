"""
Stress Test

Stress tests the AI Trading Copilot by executing
high-volume operations to validate stability,
reliability and resource handling.

Responsibilities
----------------
✓ Database Stress Test
✓ Cache Stress Test
✓ File Stress Test
✓ Configuration Stress Test
✓ CPU Stress Test
✓ Memory Stress Test
✓ Overall Stability Report
"""

from __future__ import annotations

import gc
import time
import tracemalloc
from typing import Any

from services.config.config_manager import ConfigManager
from services.database.database_manager import DatabaseManager
from services.utils.cache_manager import CacheManager
from services.utils.file_manager import FileManager


class StressTest:

    def __init__(self):

        self.results: dict[str, dict[str, Any]] = {}

    # --------------------------------------------------

    def _run(
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

            time.perf_counter() - start,

            3,

        )

        current, peak = tracemalloc.get_traced_memory()

        tracemalloc.stop()

        gc.collect()

        self.results[name] = {

            "passed": success,

            "time_sec": elapsed,

            "peak_memory_mb": round(

                peak / (1024 * 1024),

                2,

            ),

            "error": error,

        }

    # --------------------------------------------------

    def database_stress(self):

        db = DatabaseManager()

        for _ in range(10000):

            db.fetch_one(

                "SELECT 1"

            )

        db.close()

    # --------------------------------------------------

    def cache_stress(self):

        cache = CacheManager()

        for i in range(100000):

            cache.set(

                f"key{i}",

                i,

            )

        for i in range(100000):

            cache.get(

                f"key{i}"

            )

        cache.clear()

    # --------------------------------------------------

    def config_stress(self):

        config = ConfigManager()

        for i in range(5000):

            config.set(

                f"stress_{i}",

                i,

            )

            config.get(

                f"stress_{i}"

            )

    # --------------------------------------------------

    def file_stress(self):

        filename = "stress_test.tmp"

        data = "A" * 1000000

        for _ in range(20):

            FileManager.write_text(

                filename,

                data,

            )

            FileManager.read_text(

                filename,

            )

        FileManager.delete(

            filename,

        )

    # --------------------------------------------------

    def cpu_stress(self):

        total = 0

        for i in range(10000000):

            total += i

        return total

    # --------------------------------------------------

    def memory_stress(self):

        data = []

        for i in range(50000):

            data.append({

                "id": i,

                "value": str(i) * 20,

            })

        del data

    # --------------------------------------------------

    def run(self):

        self.results.clear()

        self._run(

            "Database",

            self.database_stress,

        )

        self._run(

            "Cache",

            self.cache_stress,

        )

        self._run(

            "Configuration",

            self.config_stress,

        )

        self._run(

            "File Manager",

            self.file_stress,

        )

        self._run(

            "CPU",

            self.cpu_stress,

        )

        self._run(

            "Memory",

            self.memory_stress,

        )

        return self.summary()

    # --------------------------------------------------

    def passed(self):

        return sum(

            result["passed"]

            for result in self.results.values()

        )

    # --------------------------------------------------

    def failed(self):

        return len(

            self.results

        ) - self.passed()

    # --------------------------------------------------

    def average_time(self):

        if not self.results:

            return 0

        return round(

            sum(

                result["time_sec"]

                for result in self.results.values()

            ) / len(self.results),

            3,

        )

    # --------------------------------------------------

    def summary(self):

        return {

            "tests": len(

                self.results

            ),

            "passed": self.passed(),

            "failed": self.failed(),

            "average_time_sec": self.average_time(),

            "stable": self.failed() == 0,

            "results": self.results,

        }
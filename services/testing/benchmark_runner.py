"""
Benchmark Runner

Comprehensive benchmark suite for the AI Trading Copilot.

Responsibilities
----------------
✓ CPU Benchmark
✓ Memory Benchmark
✓ Database Benchmark
✓ Cache Benchmark
✓ File I/O Benchmark
✓ Configuration Benchmark
✓ Overall Performance Score
✓ Benchmark Report
"""

from __future__ import annotations

import gc
import statistics
import time
import tracemalloc
from datetime import datetime
from typing import Any

from services.config.config_manager import ConfigManager
from services.database.database_manager import DatabaseManager
from services.utils.cache_manager import CacheManager
from services.utils.file_manager import FileManager


class BenchmarkRunner:

    def __init__(self):

        self.results: dict[str, dict[str, Any]] = {}

    # --------------------------------------------------

    def _benchmark(
        self,
        name: str,
        function,
        iterations: int = 5,
    ):

        execution_times = []

        peak_memory = []

        success = True
        error = None

        for _ in range(iterations):

            gc.collect()

            tracemalloc.start()

            start = time.perf_counter()

            try:

                function()

            except Exception as exc:

                success = False
                error = str(exc)

            elapsed = (

                time.perf_counter()

                - start

            ) * 1000

            current, peak = tracemalloc.get_traced_memory()

            tracemalloc.stop()

            execution_times.append(elapsed)

            peak_memory.append(

                peak / 1024

            )

        self.results[name] = {

            "passed": success,

            "iterations": iterations,

            "average_time_ms": round(

                statistics.mean(

                    execution_times

                ),

                3,

            ),

            "minimum_time_ms": round(

                min(

                    execution_times

                ),

                3,

            ),

            "maximum_time_ms": round(

                max(

                    execution_times

                ),

                3,

            ),

            "memory_kb": round(

                max(

                    peak_memory

                ),

                2,

            ),

            "error": error,

        }

    # --------------------------------------------------

    def cpu_benchmark(self):

        total = 0

        for i in range(

            1_000_000

        ):

            total += i * i

        return total

    # --------------------------------------------------

    def database_benchmark(self):

        db = DatabaseManager()

        for _ in range(

            1000

        ):

            db.fetch_one(

                "SELECT 1"

            )

        db.close()

    # --------------------------------------------------

    def cache_benchmark(self):

        cache = CacheManager()

        for i in range(

            10000

        ):

            cache.set(

                f"k{i}",

                i,

            )

        for i in range(

            10000

        ):

            cache.get(

                f"k{i}"

            )

        cache.clear()

    # --------------------------------------------------

    def file_benchmark(self):

        filename = "benchmark.tmp"

        FileManager.write_text(

            filename,

            "A" * 100000,

        )

        FileManager.read_text(

            filename,

        )

        FileManager.delete(

            filename,

        )

    # --------------------------------------------------

    def configuration_benchmark(self):

        config = ConfigManager()

        for i in range(

            500

        ):

            key = f"BENCH_{i}"

            config.set(

                key,

                i,

            )

            config.get(

                key,

            )

    # --------------------------------------------------

    def run(self):

        self.results.clear()

        self._benchmark(

            "CPU",

            self.cpu_benchmark,

        )

        self._benchmark(

            "Database",

            self.database_benchmark,

        )

        self._benchmark(

            "Cache",

            self.cache_benchmark,

        )

        self._benchmark(

            "File Manager",

            self.file_benchmark,

        )

        self._benchmark(

            "Configuration",

            self.configuration_benchmark,

        )

        return self.summary()

    # --------------------------------------------------

    def overall_score(self):

        if not self.results:

            return 0.0

        passed = sum(

            1

            for result in self.results.values()

            if result["passed"]

        )

        return round(

            (

                passed

                / len(

                    self.results

                )

            )

            * 100,

            2,

        )

    # --------------------------------------------------

    def fastest(self):

        return min(

            self.results.items(),

            key=lambda item: item[1][

                "average_time_ms"

            ],

        )[0]

    # --------------------------------------------------

    def slowest(self):

        return max(

            self.results.items(),

            key=lambda item: item[1][

                "average_time_ms"

            ],

        )[0]

    # --------------------------------------------------

    def summary(self):

        return {

            "timestamp": datetime.now().isoformat(),

            "overall_score": self.overall_score(),

            "benchmarks": len(

                self.results

            ),

            "fastest": (

                self.fastest()

                if self.results

                else None

            ),

            "slowest": (

                self.slowest()

                if self.results

                else None

            ),

            "results": self.results,

        }


# ------------------------------------------------------
# Standalone Execution
# ------------------------------------------------------

if __name__ == "__main__":

    benchmark = BenchmarkRunner()

    report = benchmark.run()

    print("\n" + "=" * 70)
    print(" AI TRADING COPILOT - BENCHMARK REPORT")
    print("=" * 70)
    print(f"Overall Score : {report['overall_score']}%")
    print(f"Benchmarks    : {report['benchmarks']}")
    print(f"Fastest       : {report['fastest']}")
    print(f"Slowest       : {report['slowest']}")
    print("=" * 70)
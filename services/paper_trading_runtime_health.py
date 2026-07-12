"""
Paper Trading Runtime Health Snapshot.

Converts ContinuousPaperTradingRuntime statistics into a
small, structured operational health report.

IMPORTANT:
- PAPER TRADING ONLY.
- READ-ONLY STATUS REPORTING.
- NO BROKER ORDERS ARE PLACED.
"""

from copy import deepcopy


class PaperTradingRuntimeHealth:
    """
    Build a read-only health snapshot from runtime statistics.
    """

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    NOT_STARTED = "NOT_STARTED"

    def __init__(
        self,
        runtime,
    ):
        if runtime is None:
            raise ValueError(
                "runtime is required."
            )

        get_stats = getattr(
            runtime,
            "get_stats",
            None,
        )

        if not callable(
            get_stats
        ):
            raise ValueError(
                "runtime must provide a callable get_stats method."
            )

        self.runtime = runtime

    @staticmethod
    def _non_negative_integer(
        value,
    ):
        if isinstance(
            value,
            bool,
        ):
            return 0

        try:
            value = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0

        return max(
            0,
            value,
        )

    @staticmethod
    def _normalize_startup_status(
        value,
    ):
        if value is None:
            return "NOT_STARTED"

        value = str(
            value
        ).strip().upper()

        if not value:
            return "NOT_STARTED"

        return value

    def snapshot(
        self,
    ):
        """
        Return a structured runtime health snapshot.
        """

        stats = (
            self.runtime.get_stats()
        )

        if not isinstance(
            stats,
            dict,
        ):
            raise RuntimeError(
                "runtime.get_stats() must return a dictionary."
            )

        stats = deepcopy(
            stats
        )

        startup_status = (
            self._normalize_startup_status(
                stats.get(
                    "startup_status"
                )
            )
        )

        cycles_started = (
            self._non_negative_integer(
                stats.get(
                    "cycles_started"
                )
            )
        )

        cycles_completed = (
            self._non_negative_integer(
                stats.get(
                    "cycles_completed"
                )
            )
        )

        cycles_with_errors = (
            self._non_negative_integer(
                stats.get(
                    "cycles_with_errors"
                )
            )
        )

        opportunity_failures = (
            self._non_negative_integer(
                stats.get(
                    "opportunity_failures"
                )
            )
        )

        monitoring_failures = (
            self._non_negative_integer(
                stats.get(
                    "monitoring_failures"
                )
            )
        )

        total_failures = (
            cycles_with_errors
            + opportunity_failures
            + monitoring_failures
        )

        running = bool(
            stats.get(
                "running",
                False,
            )
        )

        interrupted = bool(
            stats.get(
                "interrupted",
                False,
            )
        )

        if startup_status == "FAILED":
            health_status = (
                self.FAILED
            )

        elif total_failures > 0:
            health_status = (
                self.DEGRADED
            )

        elif (
            startup_status
            in {
                "NOT_STARTED",
                "PENDING",
            }
            and cycles_started == 0
        ):
            health_status = (
                self.NOT_STARTED
            )

        else:
            health_status = (
                self.HEALTHY
            )

        return {
            "health_status": (
                health_status
            ),
            "paper_trading_only": True,
            "real_order_execution": False,
            "running": running,
            "interrupted": interrupted,
            "startup": {
                "status": (
                    startup_status
                ),
                "result": deepcopy(
                    stats.get(
                        "startup_result"
                    )
                ),
                "error": (
                    stats.get(
                        "startup_error"
                    )
                ),
            },
            "cycles": {
                "started": (
                    cycles_started
                ),
                "completed": (
                    cycles_completed
                ),
                "with_errors": (
                    cycles_with_errors
                ),
            },
            "operations": {
                "opportunity_successes": (
                    self._non_negative_integer(
                        stats.get(
                            "opportunity_successes"
                        )
                    )
                ),
                "opportunity_failures": (
                    opportunity_failures
                ),
                "monitoring_successes": (
                    self._non_negative_integer(
                        stats.get(
                            "monitoring_successes"
                        )
                    )
                ),
                "monitoring_failures": (
                    monitoring_failures
                ),
            },
            "total_failures": (
                total_failures
            ),
            "raw_stats": stats,
        }

    def get_health(
        self,
    ):
        """
        Alias for snapshot().
        """

        return self.snapshot()
"""
Continuous Paper Trading Runtime.

Coordinates injected operations:

1. Optional startup operation
2. Opportunity cycle
3. Position-monitoring cycle
4. Wait
5. Repeat

Safety properties:
- Paper-trading orchestration only.
- No broker order placement.
- No overlapping runtime cycles.
- Graceful stop support.
- KeyboardInterrupt handling.
- Per-operation error isolation.
- Startup failure is fail-closed.
- Monotonic interval timing.
- Optional maximum cycle count.
"""

from copy import deepcopy
import math
import threading
import time


class ContinuousPaperTradingRuntime:

    def __init__(
        self,
        opportunity_cycle,
        monitoring_cycle,
        *,
        startup_operation=None,
        interval_seconds=60.0,
        sleep_function=time.sleep,
        monotonic_function=time.monotonic,
    ):
        if not callable(
            opportunity_cycle
        ):
            raise ValueError(
                "opportunity_cycle must be callable."
            )

        if not callable(
            monitoring_cycle
        ):
            raise ValueError(
                "monitoring_cycle must be callable."
            )

        if (
            startup_operation is not None
            and not callable(
                startup_operation
            )
        ):
            raise ValueError(
                "startup_operation must be callable."
            )

        if not callable(
            sleep_function
        ):
            raise ValueError(
                "sleep_function must be callable."
            )

        if not callable(
            monotonic_function
        ):
            raise ValueError(
                "monotonic_function must be callable."
            )

        self.interval_seconds = (
            self._validate_interval(
                interval_seconds
            )
        )

        self.opportunity_cycle = (
            opportunity_cycle
        )

        self.monitoring_cycle = (
            monitoring_cycle
        )

        self.startup_operation = (
            startup_operation
        )

        self.sleep_function = (
            sleep_function
        )

        self.monotonic_function = (
            monotonic_function
        )

        self._stop_event = (
            threading.Event()
        )

        self._cycle_lock = (
            threading.Lock()
        )

        self._running = False

        self._stats = (
            self._new_stats()
        )

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def _validate_interval(
        value,
    ):
        if isinstance(
            value,
            bool,
        ):
            raise ValueError(
                "interval_seconds must be numeric."
            )

        try:
            value = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "interval_seconds must be numeric."
            ) from exc

        if not math.isfinite(
            value
        ):
            raise ValueError(
                "interval_seconds must be finite."
            )

        if value < 0:
            raise ValueError(
                "interval_seconds cannot be negative."
            )

        return value

    @staticmethod
    def _validate_max_cycles(
        max_cycles,
    ):
        if max_cycles is None:
            return None

        if isinstance(
            max_cycles,
            bool,
        ):
            raise ValueError(
                "max_cycles must be a positive integer."
            )

        if not isinstance(
            max_cycles,
            int,
        ):
            raise ValueError(
                "max_cycles must be a positive integer."
            )

        if max_cycles <= 0:
            raise ValueError(
                "max_cycles must be greater than zero."
            )

        return max_cycles

    # ---------------------------------------------------------
    # STATS
    # ---------------------------------------------------------

    @staticmethod
    def _new_stats():
        return {
            "cycles_started": 0,
            "cycles_completed": 0,
            "cycles_with_errors": 0,
            "opportunity_successes": 0,
            "opportunity_failures": 0,
            "monitoring_successes": 0,
            "monitoring_failures": 0,
            "stop_requested": False,
            "interrupted": False,
            "running": False,
            "last_cycle": None,
            "startup_status": "NOT_RUN",
            "startup_result": None,
            "startup_error": None,
        }

    def reset_stats(
        self,
    ):
        if self._running:
            raise RuntimeError(
                "Cannot reset statistics while runtime is running."
            )

        self._stats = (
            self._new_stats()
        )

        return self.get_stats()

    def get_stats(
        self,
    ):
        result = deepcopy(
            self._stats
        )

        result[
            "running"
        ] = self._running

        result[
            "stop_requested"
        ] = (
            self._stop_event.is_set()
        )

        return result

    # ---------------------------------------------------------
    # STOP CONTROL
    # ---------------------------------------------------------

    def request_stop(
        self,
    ):
        self._stop_event.set()

        self._stats[
            "stop_requested"
        ] = True

    def clear_stop_request(
        self,
    ):
        if self._running:
            raise RuntimeError(
                "Cannot clear stop request while runtime is running."
            )

        self._stop_event.clear()

        self._stats[
            "stop_requested"
        ] = False

    def is_stop_requested(
        self,
    ):
        return (
            self._stop_event.is_set()
        )

    def is_running(
        self,
    ):
        return self._running

    # ---------------------------------------------------------
    # OPERATION EXECUTION
    # ---------------------------------------------------------

    @staticmethod
    def _run_operation(
        operation,
        operation_name,
    ):
        try:
            result = operation()

            return {
                "name": operation_name,
                "status": "COMPLETED",
                "result": deepcopy(
                    result
                ),
                "error": None,
            }

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            return {
                "name": operation_name,
                "status": "ERROR",
                "result": None,
                "error": str(
                    exc
                ),
            }

    # ---------------------------------------------------------
    # STARTUP OPERATION
    # ---------------------------------------------------------

    def _run_startup_operation(
        self,
    ):
        """
        Run the optional startup operation once before
        continuous paper-trading cycles begin.

        Startup failure is fail-closed.
        """

        if self.startup_operation is None:
            self._stats[
                "startup_status"
            ] = "NOT_CONFIGURED"

            self._stats[
                "startup_result"
            ] = None

            self._stats[
                "startup_error"
            ] = None

            return True

        try:
            result = (
                self.startup_operation()
            )

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            self._stats[
                "startup_status"
            ] = "ERROR"

            self._stats[
                "startup_result"
            ] = None

            self._stats[
                "startup_error"
            ] = str(
                exc
            )

            return False

        self._stats[
            "startup_result"
        ] = deepcopy(
            result
        )

        self._stats[
            "startup_error"
        ] = None

        if (
            isinstance(
                result,
                dict,
            )
            and result.get(
                "success"
            ) is False
        ):
            self._stats[
                "startup_status"
            ] = "FAILED"

            self._stats[
                "startup_error"
            ] = result.get(
                "error"
            )

            return False

        self._stats[
            "startup_status"
        ] = "COMPLETED"

        return True

    # ---------------------------------------------------------
    # ONE COMPLETE CYCLE
    # ---------------------------------------------------------

    def run_cycle(
        self,
    ):
        """
        Run one non-overlapping paper-trading cycle.

        The opportunity operation and monitoring operation are isolated:
        failure in one does not prevent the other from running.
        """

        if not self._cycle_lock.acquire(
            blocking=False
        ):
            raise RuntimeError(
                "A paper-trading cycle is already running."
            )

        try:
            cycle_number = (
                self._stats[
                    "cycles_started"
                ]
                + 1
            )

            started_at = (
                self.monotonic_function()
            )

            self._stats[
                "cycles_started"
            ] += 1

            opportunity = (
                self._run_operation(
                    self.opportunity_cycle,
                    "OPPORTUNITY",
                )
            )

            if (
                opportunity[
                    "status"
                ]
                == "COMPLETED"
            ):
                self._stats[
                    "opportunity_successes"
                ] += 1

            else:
                self._stats[
                    "opportunity_failures"
                ] += 1

            monitoring = (
                self._run_operation(
                    self.monitoring_cycle,
                    "MONITORING",
                )
            )

            if (
                monitoring[
                    "status"
                ]
                == "COMPLETED"
            ):
                self._stats[
                    "monitoring_successes"
                ] += 1

            else:
                self._stats[
                    "monitoring_failures"
                ] += 1

            finished_at = (
                self.monotonic_function()
            )

            duration_seconds = max(
                0.0,
                float(
                    finished_at
                    - started_at
                ),
            )

            has_errors = (
                opportunity[
                    "status"
                ]
                == "ERROR"
                or monitoring[
                    "status"
                ]
                == "ERROR"
            )

            cycle_report = {
                "cycle_number": cycle_number,
                "status": (
                    "COMPLETED_WITH_ERRORS"
                    if has_errors
                    else "COMPLETED"
                ),
                "started_at_monotonic": (
                    started_at
                ),
                "finished_at_monotonic": (
                    finished_at
                ),
                "duration_seconds": (
                    duration_seconds
                ),
                "opportunity": (
                    opportunity
                ),
                "monitoring": (
                    monitoring
                ),
            }

            self._stats[
                "cycles_completed"
            ] += 1

            if has_errors:
                self._stats[
                    "cycles_with_errors"
                ] += 1

            self._stats[
                "last_cycle"
            ] = deepcopy(
                cycle_report
            )

            return deepcopy(
                cycle_report
            )

        finally:
            self._cycle_lock.release()

    # ---------------------------------------------------------
    # WAIT
    # ---------------------------------------------------------

    def _wait_until_next_cycle(
        self,
        cycle_started_at,
    ):
        """
        Wait only for the remaining interval.
        """

        elapsed = (
            self.monotonic_function()
            - cycle_started_at
        )

        remaining = max(
            0.0,
            self.interval_seconds
            - elapsed,
        )

        if (
            remaining > 0
            and not self.is_stop_requested()
        ):
            self.sleep_function(
                remaining
            )

        return remaining

    # ---------------------------------------------------------
    # CONTINUOUS RUNTIME
    # ---------------------------------------------------------

    def run(
        self,
        *,
        max_cycles=None,
    ):
        """
        Run continuously until:
        - request_stop() is called,
        - KeyboardInterrupt occurs,
        - max_cycles is reached.

        The optional startup operation runs once before
        the first cycle of each run.

        Returns final runtime statistics.
        """

        max_cycles = (
            self._validate_max_cycles(
                max_cycles
            )
        )

        if self._running:
            raise RuntimeError(
                "Continuous paper-trading runtime is already running."
            )

        self._running = True

        self._stats[
            "running"
        ] = True

        completed_in_this_run = 0

        try:
            startup_allowed = (
                self._run_startup_operation()
            )

            if not startup_allowed:
                return self.get_stats()

            while not self.is_stop_requested():

                cycle_started_at = (
                    self.monotonic_function()
                )

                try:
                    self.run_cycle()

                except KeyboardInterrupt:
                    self._stats[
                        "interrupted"
                    ] = True

                    self.request_stop()

                    break

                completed_in_this_run += 1

                if (
                    max_cycles is not None
                    and completed_in_this_run
                    >= max_cycles
                ):
                    break

                if self.is_stop_requested():
                    break

                try:
                    self._wait_until_next_cycle(
                        cycle_started_at
                    )

                except KeyboardInterrupt:
                    self._stats[
                        "interrupted"
                    ] = True

                    self.request_stop()

                    break

        finally:
            self._running = False

            self._stats[
                "running"
            ] = False

        return self.get_stats()

    # ---------------------------------------------------------
    # ALIAS
    # ---------------------------------------------------------

    def run_forever(
        self,
    ):
        return self.run(
            max_cycles=None
        )
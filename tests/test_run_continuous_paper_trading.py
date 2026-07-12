import pytest

import run_continuous_paper_trading as entry


# ============================================================
# FAKES
# ============================================================


class FakeAdapter:

    def __init__(
        self,
        **kwargs,
    ):
        self.kwargs = kwargs

        self.opportunity_calls = 0
        self.monitoring_calls = 0

    def run_opportunity_cycle(
        self,
    ):
        self.opportunity_calls += 1

        return {
            "cycle": "OPPORTUNITY",
            "status": "COMPLETED",
            "success": True,
            "returncode": 0,
            "stdout": "Opportunity complete",
            "stderr": "",
            "error": None,
        }

    def run_monitoring_cycle(
        self,
    ):
        self.monitoring_calls += 1

        return {
            "cycle": "MONITORING",
            "status": "COMPLETED",
            "success": True,
            "returncode": 0,
            "stdout": "Monitoring complete",
            "stderr": "",
            "error": None,
        }


class FakeRuntime:

    def __init__(
        self,
        opportunity_cycle,
        monitoring_cycle,
        interval_seconds,
    ):
        self.opportunity_cycle = (
            opportunity_cycle
        )

        self.monitoring_cycle = (
            monitoring_cycle
        )

        self.interval_seconds = (
            interval_seconds
        )

        self.max_cycles = None

    def run(
        self,
        *,
        max_cycles=None,
    ):
        self.max_cycles = (
            max_cycles
        )

        self.opportunity_cycle()
        self.monitoring_cycle()

        return {
            "cycles_started": 1,
            "cycles_completed": 1,
            "cycles_with_errors": 0,
            "opportunity_successes": 1,
            "opportunity_failures": 0,
            "monitoring_successes": 1,
            "monitoring_failures": 0,
            "interrupted": False,
        }


# ============================================================
# CONFIG
# ============================================================


def test_default_config(
    monkeypatch,
):
    monkeypatch.delenv(
        "PAPER_TRADING_INTERVAL_SECONDS",
        raising=False,
    )

    monkeypatch.delenv(
        "PAPER_TRADING_SCRIPT_TIMEOUT_SECONDS",
        raising=False,
    )

    config = (
        entry.get_runtime_config()
    )

    assert (
        config[
            "interval_seconds"
        ]
        == 60.0
    )

    assert (
        config[
            "timeout_seconds"
        ]
        == 300.0
    )


def test_interval_from_environment(
    monkeypatch,
):
    monkeypatch.setenv(
        "PAPER_TRADING_INTERVAL_SECONDS",
        "30",
    )

    config = (
        entry.get_runtime_config()
    )

    assert (
        config[
            "interval_seconds"
        ]
        == 30.0
    )


def test_timeout_from_environment(
    monkeypatch,
):
    monkeypatch.setenv(
        "PAPER_TRADING_SCRIPT_TIMEOUT_SECONDS",
        "120",
    )

    config = (
        entry.get_runtime_config()
    )

    assert (
        config[
            "timeout_seconds"
        ]
        == 120.0
    )


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "abc",
    ],
)
def test_invalid_interval_environment(
    monkeypatch,
    value,
):
    monkeypatch.setenv(
        "PAPER_TRADING_INTERVAL_SECONDS",
        value,
    )

    with pytest.raises(
        ValueError
    ):
        entry.get_runtime_config()


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "abc",
    ],
)
def test_invalid_timeout_environment(
    monkeypatch,
    value,
):
    monkeypatch.setenv(
        "PAPER_TRADING_SCRIPT_TIMEOUT_SECONDS",
        value,
    )

    with pytest.raises(
        ValueError
    ):
        entry.get_runtime_config()


# ============================================================
# CYCLE WRAPPER
# ============================================================


def test_cycle_wrapper_returns_success():

    source = {
        "status": "COMPLETED",
        "success": True,
        "stdout": "",
        "stderr": "",
    }

    cycle = (
        entry.create_cycle_callable(
            lambda: source,
            "TEST",
        )
    )

    assert (
        cycle()
        is source
    )


def test_cycle_wrapper_rejects_non_callable():

    with pytest.raises(
        ValueError
    ):
        entry.create_cycle_callable(
            None,
            "TEST",
        )


def test_cycle_wrapper_rejects_invalid_result():

    cycle = (
        entry.create_cycle_callable(
            lambda: None,
            "TEST",
        )
    )

    with pytest.raises(
        RuntimeError,
        match="invalid data",
    ):
        cycle()


def test_cycle_wrapper_raises_on_failed_result():

    cycle = (
        entry.create_cycle_callable(
            lambda: {
                "status": "FAILED",
                "success": False,
                "error": "Child failed",
                "stdout": "",
                "stderr": "",
            },
            "TEST",
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Child failed",
    ):
        cycle()


def test_cycle_wrapper_uses_fallback_error():

    cycle = (
        entry.create_cycle_callable(
            lambda: {
                "status": "FAILED",
                "success": False,
                "error": None,
                "stdout": "",
                "stderr": "",
            },
            "TEST",
        )
    )

    with pytest.raises(
        RuntimeError,
        match="TEST cycle failed",
    ):
        cycle()


# ============================================================
# OUTPUT
# ============================================================


def test_header_prints_paper_only(
    capsys,
):
    entry.print_header(
        {
            "interval_seconds": 60.0,
            "timeout_seconds": 300.0,
        }
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "CONTINUOUS PAPER TRADING RUNTIME"
        in output
    )

    assert (
        "PAPER TRADING ONLY"
        in output
    )

    assert (
        "Real Order Execution: DISABLED"
        in output
    )


def test_subprocess_stdout_printed(
    capsys,
):
    entry._print_subprocess_output(
        "TEST",
        {
            "status": "COMPLETED",
            "stdout": "Hello",
            "stderr": "",
        },
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Hello"
        in output
    )


def test_subprocess_stderr_printed(
    capsys,
):
    entry._print_subprocess_output(
        "TEST",
        {
            "status": "FAILED",
            "stdout": "",
            "stderr": "Failure",
        },
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Failure"
        in output
    )


def test_invalid_subprocess_result_printed(
    capsys,
):
    entry._print_subprocess_output(
        "TEST",
        None,
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Invalid result"
        in output
    )


# ============================================================
# BUILD RUNTIME
# ============================================================


def test_build_runtime_creates_adapter():

    created = {}

    def adapter_factory(
        **kwargs,
    ):
        adapter = (
            FakeAdapter(
                **kwargs
            )
        )

        created[
            "adapter"
        ] = adapter

        return adapter

    runtime, adapter = (
        entry.build_runtime(
            config={
                "interval_seconds": 15.0,
                "timeout_seconds": 120.0,
            },
            adapter_factory=(
                adapter_factory
            ),
            runtime_factory=(
                FakeRuntime
            ),
        )
    )

    assert (
        adapter
        is created[
            "adapter"
        ]
    )

    assert (
        runtime.interval_seconds
        == 15.0
    )


def test_build_runtime_passes_timeout():

    created = {}

    def adapter_factory(
        **kwargs,
    ):
        created.update(
            kwargs
        )

        return FakeAdapter(
            **kwargs
        )

    entry.build_runtime(
        config={
            "interval_seconds": 60.0,
            "timeout_seconds": 123.0,
        },
        adapter_factory=(
            adapter_factory
        ),
        runtime_factory=(
            FakeRuntime
        ),
    )

    assert (
        created[
            "timeout_seconds"
        ]
        == 123.0
    )


def test_build_runtime_uses_correct_scripts():

    created = {}

    def adapter_factory(
        **kwargs,
    ):
        created.update(
            kwargs
        )

        return FakeAdapter(
            **kwargs
        )

    entry.build_runtime(
        config={
            "interval_seconds": 60.0,
            "timeout_seconds": 300.0,
        },
        adapter_factory=(
            adapter_factory
        ),
        runtime_factory=(
            FakeRuntime
        ),
    )

    assert (
        created[
            "opportunity_script"
        ]
        == "live_option_decision_nifty.py"
    )

    assert (
        created[
            "monitoring_script"
        ]
        == "monitor_paper_positions.py"
    )


# ============================================================
# MAIN
# ============================================================


def test_main_returns_zero():

    result = (
        entry.main(
            max_cycles=1,
            config={
                "interval_seconds": 0.1,
                "timeout_seconds": 10.0,
            },
            adapter_factory=(
                FakeAdapter
            ),
            runtime_factory=(
                FakeRuntime
            ),
        )
    )

    assert result == 0


def test_main_passes_max_cycles():

    created = {}

    class TrackingRuntime(
        FakeRuntime
    ):

        def run(
            self,
            *,
            max_cycles=None,
        ):
            created[
                "max_cycles"
            ] = max_cycles

            return super().run(
                max_cycles=max_cycles
            )

    result = (
        entry.main(
            max_cycles=5,
            config={
                "interval_seconds": 1.0,
                "timeout_seconds": 10.0,
            },
            adapter_factory=(
                FakeAdapter
            ),
            runtime_factory=(
                TrackingRuntime
            ),
        )
    )

    assert result == 0

    assert (
        created[
            "max_cycles"
        ]
        == 5
    )


def test_main_runs_both_cycles():

    created = {}

    def adapter_factory(
        **kwargs,
    ):
        adapter = (
            FakeAdapter(
                **kwargs
            )
        )

        created[
            "adapter"
        ] = adapter

        return adapter

    result = (
        entry.main(
            max_cycles=1,
            config={
                "interval_seconds": 1.0,
                "timeout_seconds": 10.0,
            },
            adapter_factory=(
                adapter_factory
            ),
            runtime_factory=(
                FakeRuntime
            ),
        )
    )

    assert result == 0

    assert (
        created[
            "adapter"
        ].opportunity_calls
        == 1
    )

    assert (
        created[
            "adapter"
        ].monitoring_calls
        == 1
    )


def test_main_returns_one_on_build_error():

    def failing_adapter(
        **kwargs,
    ):
        raise RuntimeError(
            "Build failed"
        )

    result = (
        entry.main(
            config={
                "interval_seconds": 1.0,
                "timeout_seconds": 10.0,
            },
            adapter_factory=(
                failing_adapter
            ),
            runtime_factory=(
                FakeRuntime
            ),
        )
    )

    assert result == 1


def test_main_handles_keyboard_interrupt():

    class InterruptingRuntime(
        FakeRuntime
    ):

        def run(
            self,
            *,
            max_cycles=None,
        ):
            raise KeyboardInterrupt()

    result = (
        entry.main(
            config={
                "interval_seconds": 1.0,
                "timeout_seconds": 10.0,
            },
            adapter_factory=(
                FakeAdapter
            ),
            runtime_factory=(
                InterruptingRuntime
            ),
        )
    )

    assert result == 0


def test_main_output_confirms_no_real_order(
    capsys,
):

    entry.main(
        max_cycles=1,
        config={
            "interval_seconds": 1.0,
            "timeout_seconds": 10.0,
        },
        adapter_factory=(
            FakeAdapter
        ),
        runtime_factory=(
            FakeRuntime
        ),
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "NO REAL ORDER WAS PLACED"
        in output
    )


# ============================================================
# FINAL STATS
# ============================================================


def test_final_stats_printed(
    capsys,
):

    entry.print_final_stats(
        {
            "cycles_started": 2,
            "cycles_completed": 2,
            "cycles_with_errors": 1,
            "opportunity_successes": 1,
            "opportunity_failures": 1,
            "monitoring_successes": 2,
            "monitoring_failures": 0,
            "interrupted": False,
        }
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Cycles Completed: 2"
        in output
    )

    assert (
        "Cycles With Errors: 1"
        in output
    )

    assert (
        "Opportunity Failures: 1"
        in output
    )

    assert (
        "Monitoring Successes: 2"
        in output
    )
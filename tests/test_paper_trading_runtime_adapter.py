import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.paper_trading_runtime_adapter import (
    PaperTradingRuntimeAdapter,
)


# ============================================================
# HELPERS
# ============================================================


class FakeRunner:

    def __init__(
        self,
        *,
        returncode=0,
        stdout="",
        stderr="",
        error=None,
    ):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.error = error
        self.calls = []

    def __call__(
        self,
        command,
        **kwargs,
    ):
        self.calls.append(
            {
                "command": command,
                "kwargs": kwargs,
            }
        )

        if self.error:
            raise self.error

        return SimpleNamespace(
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
        )


def make_adapter(
    *,
    runner=None,
    working_directory=None,
):
    if runner is None:
        runner = FakeRunner()

    if working_directory is None:
        working_directory = Path.cwd()

    adapter = (
        PaperTradingRuntimeAdapter(
            opportunity_script=(
                "live_option_decision_nifty.py"
            ),
            monitoring_script=(
                "monitor_paper_positions.py"
            ),
            python_executable=(
                "python-test"
            ),
            working_directory=(
                working_directory
            ),
            timeout_seconds=120,
            subprocess_runner=(
                runner
            ),
        )
    )

    return adapter, runner


# ============================================================
# CONSTRUCTOR
# ============================================================


def test_default_python_executable():

    adapter = (
        PaperTradingRuntimeAdapter()
    )

    assert (
        adapter.python_executable
        == sys.executable
    )


def test_custom_python_executable():

    adapter = (
        PaperTradingRuntimeAdapter(
            python_executable="custom-python"
        )
    )

    assert (
        adapter.python_executable
        == "custom-python"
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        123,
    ],
)
def test_invalid_opportunity_script_rejected(
    value,
):
    with pytest.raises(
        ValueError
    ):
        PaperTradingRuntimeAdapter(
            opportunity_script=value
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        123,
    ],
)
def test_invalid_monitoring_script_rejected(
    value,
):
    with pytest.raises(
        ValueError
    ):
        PaperTradingRuntimeAdapter(
            monitoring_script=value
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        True,
        False,
        "abc",
        None,
    ],
)
def test_invalid_timeout_rejected(
    value,
):
    with pytest.raises(
        ValueError
    ):
        PaperTradingRuntimeAdapter(
            timeout_seconds=value
        )


def test_non_callable_runner_rejected():

    with pytest.raises(
        ValueError
    ):
        PaperTradingRuntimeAdapter(
            subprocess_runner=None
        )


# ============================================================
# OPPORTUNITY CYCLE
# ============================================================


def test_opportunity_cycle_runs_correct_script():

    adapter, runner = (
        make_adapter()
    )

    adapter.run_opportunity_cycle()

    command = (
        runner.calls[
            0
        ][
            "command"
        ]
    )

    assert (
        command[
            0
        ]
        == "python-test"
    )

    assert (
        command[
            1
        ].endswith(
            "live_option_decision_nifty.py"
        )
    )


def test_opportunity_cycle_name():

    adapter, _ = (
        make_adapter()
    )

    result = (
        adapter.run_opportunity_cycle()
    )

    assert (
        result[
            "cycle"
        ]
        == "OPPORTUNITY"
    )


# ============================================================
# MONITORING CYCLE
# ============================================================


def test_monitoring_cycle_runs_correct_script():

    adapter, runner = (
        make_adapter()
    )

    adapter.run_monitoring_cycle()

    command = (
        runner.calls[
            0
        ][
            "command"
        ]
    )

    assert (
        command[
            1
        ].endswith(
            "monitor_paper_positions.py"
        )
    )


def test_monitoring_cycle_name():

    adapter, _ = (
        make_adapter()
    )

    result = (
        adapter.run_monitoring_cycle()
    )

    assert (
        result[
            "cycle"
        ]
        == "MONITORING"
    )


# ============================================================
# SUCCESS
# ============================================================


def test_successful_script_returns_completed():

    runner = (
        FakeRunner(
            returncode=0,
            stdout="Success",
        )
    )

    adapter, _ = (
        make_adapter(
            runner=runner
        )
    )

    result = (
        adapter.run_opportunity_cycle()
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED"
    )

    assert (
        result[
            "success"
        ]
        is True
    )

    assert (
        result[
            "returncode"
        ]
        == 0
    )


def test_stdout_is_captured():

    runner = (
        FakeRunner(
            stdout=(
                "Decision: MARKET_CLOSED"
            )
        )
    )

    adapter, _ = (
        make_adapter(
            runner=runner
        )
    )

    result = (
        adapter.run_opportunity_cycle()
    )

    assert (
        result[
            "stdout"
        ]
        == "Decision: MARKET_CLOSED"
    )


def test_stderr_is_captured():

    runner = (
        FakeRunner(
            stderr="Warning"
        )
    )

    adapter, _ = (
        make_adapter(
            runner=runner
        )
    )

    result = (
        adapter.run_monitoring_cycle()
    )

    assert (
        result[
            "stderr"
        ]
        == "Warning"
    )


# ============================================================
# NON-ZERO EXIT
# ============================================================


def test_nonzero_exit_returns_failed():

    runner = (
        FakeRunner(
            returncode=1,
            stderr="Failure",
        )
    )

    adapter, _ = (
        make_adapter(
            runner=runner
        )
    )

    result = (
        adapter.run_opportunity_cycle()
    )

    assert (
        result[
            "status"
        ]
        == "FAILED"
    )

    assert (
        result[
            "success"
        ]
        is False
    )

    assert (
        result[
            "returncode"
        ]
        == 1
    )


def test_nonzero_exit_contains_error():

    runner = (
        FakeRunner(
            returncode=2
        )
    )

    adapter, _ = (
        make_adapter(
            runner=runner
        )
    )

    result = (
        adapter.run_monitoring_cycle()
    )

    assert (
        "code 2"
        in result[
            "error"
        ]
    )


# ============================================================
# SUBPROCESS OPTIONS
# ============================================================


def test_capture_output_enabled():

    adapter, runner = (
        make_adapter()
    )

    adapter.run_opportunity_cycle()

    kwargs = (
        runner.calls[
            0
        ][
            "kwargs"
        ]
    )

    assert (
        kwargs[
            "capture_output"
        ]
        is True
    )


def test_text_mode_enabled():

    adapter, runner = (
        make_adapter()
    )

    adapter.run_opportunity_cycle()

    kwargs = (
        runner.calls[
            0
        ][
            "kwargs"
        ]
    )

    assert (
        kwargs[
            "text"
        ]
        is True
    )


def test_check_disabled():

    adapter, runner = (
        make_adapter()
    )

    adapter.run_opportunity_cycle()

    kwargs = (
        runner.calls[
            0
        ][
            "kwargs"
        ]
    )

    assert (
        kwargs[
            "check"
        ]
        is False
    )


def test_timeout_forwarded():

    adapter, runner = (
        make_adapter()
    )

    adapter.run_opportunity_cycle()

    kwargs = (
        runner.calls[
            0
        ][
            "kwargs"
        ]
    )

    assert (
        kwargs[
            "timeout"
        ]
        == 120.0
    )


def test_working_directory_forwarded(
    tmp_path,
):

    adapter, runner = (
        make_adapter(
            working_directory=tmp_path
        )
    )

    adapter.run_opportunity_cycle()

    kwargs = (
        runner.calls[
            0
        ][
            "kwargs"
        ]
    )

    assert (
        kwargs[
            "cwd"
        ]
        == str(
            tmp_path.resolve()
        )
    )


# ============================================================
# TIMEOUT
# ============================================================


def test_timeout_returns_timeout_status():

    error = (
        subprocess.TimeoutExpired(
            cmd=[
                "python",
                "script.py",
            ],
            timeout=120,
        )
    )

    runner = (
        FakeRunner(
            error=error
        )
    )

    adapter, _ = (
        make_adapter(
            runner=runner
        )
    )

    result = (
        adapter.run_opportunity_cycle()
    )

    assert (
        result[
            "status"
        ]
        == "TIMEOUT"
    )

    assert (
        result[
            "success"
        ]
        is False
    )


def test_timeout_has_no_returncode():

    error = (
        subprocess.TimeoutExpired(
            cmd="test",
            timeout=120,
        )
    )

    runner = (
        FakeRunner(
            error=error
        )
    )

    adapter, _ = (
        make_adapter(
            runner=runner
        )
    )

    result = (
        adapter.run_monitoring_cycle()
    )

    assert (
        result[
            "returncode"
        ]
        is None
    )


# ============================================================
# GENERAL EXECUTION ERROR
# ============================================================


def test_execution_exception_returns_error():

    runner = (
        FakeRunner(
            error=OSError(
                "Unable to start process"
            )
        )
    )

    adapter, _ = (
        make_adapter(
            runner=runner
        )
    )

    result = (
        adapter.run_opportunity_cycle()
    )

    assert (
        result[
            "status"
        ]
        == "ERROR"
    )

    assert (
        result[
            "success"
        ]
        is False
    )

    assert (
        result[
            "error"
        ]
        == "Unable to start process"
    )


# ============================================================
# ISOLATION
# ============================================================


def test_system_exit_code_isolated_as_returncode():

    runner = (
        FakeRunner(
            returncode=1
        )
    )

    adapter, _ = (
        make_adapter(
            runner=runner
        )
    )

    result = (
        adapter.run_opportunity_cycle()
    )

    assert (
        result[
            "returncode"
        ]
        == 1
    )

    assert (
        result[
            "status"
        ]
        == "FAILED"
    )


def test_adapter_does_not_import_target_scripts():

    adapter, _ = (
        make_adapter()
    )

    assert (
        adapter.opportunity_script
        == "live_option_decision_nifty.py"
    )

    assert (
        adapter.monitoring_script
        == "monitor_paper_positions.py"
    )


# ============================================================
# PATH RESOLUTION
# ============================================================


def test_relative_script_resolves_from_working_directory(
    tmp_path,
):

    adapter, _ = (
        make_adapter(
            working_directory=tmp_path
        )
    )

    path = (
        adapter._resolve_script(
            "example.py"
        )
    )

    assert (
        path
        == (
            tmp_path
            / "example.py"
        ).resolve()
    )


def test_absolute_script_remains_absolute(
    tmp_path,
):

    absolute = (
        tmp_path
        / "example.py"
    ).resolve()

    adapter, _ = (
        make_adapter()
    )

    result = (
        adapter._resolve_script(
            absolute
        )
    )

    assert (
        result
        == absolute
    )
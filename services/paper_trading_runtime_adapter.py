"""
Paper Trading Runtime Adapter.

Runs existing standalone entry-point scripts as isolated subprocesses.

Purpose:
- Preserve legacy/module-scope entry points without importing them.
- Prevent SystemExit inside a child script from terminating the runtime.
- Capture stdout and stderr.
- Convert subprocess results into structured dictionaries.
- Provide callables compatible with ContinuousPaperTradingRuntime.

IMPORTANT:
- This adapter does not place broker orders.
- It only launches configured Python scripts.
"""

from pathlib import Path
import subprocess
import sys


class PaperTradingRuntimeAdapter:

    def __init__(
        self,
        *,
        opportunity_script="live_option_decision_nifty.py",
        monitoring_script="monitor_paper_positions.py",
        python_executable=None,
        working_directory=None,
        timeout_seconds=300.0,
        subprocess_runner=subprocess.run,
    ):
        self.opportunity_script = self._validate_script_name(
            opportunity_script,
            "opportunity_script",
        )

        self.monitoring_script = self._validate_script_name(
            monitoring_script,
            "monitoring_script",
        )

        self.python_executable = (
            str(python_executable)
            if python_executable is not None
            else sys.executable
        )

        if not self.python_executable.strip():
            raise ValueError(
                "python_executable cannot be empty."
            )

        self.working_directory = (
            Path(working_directory).resolve()
            if working_directory is not None
            else Path.cwd().resolve()
        )

        self.timeout_seconds = self._validate_timeout(
            timeout_seconds
        )

        if not callable(subprocess_runner):
            raise ValueError(
                "subprocess_runner must be callable."
            )

        self.subprocess_runner = subprocess_runner

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def _validate_script_name(
        value,
        field_name,
    ):
        if not isinstance(value, (str, Path)):
            raise ValueError(
                f"{field_name} must be a path."
            )

        value = str(value).strip()

        if not value:
            raise ValueError(
                f"{field_name} cannot be empty."
            )

        return value

    @staticmethod
    def _validate_timeout(
        value,
    ):
        if isinstance(value, bool):
            raise ValueError(
                "timeout_seconds must be a positive number."
            )

        try:
            value = float(value)

        except (TypeError, ValueError) as exc:
            raise ValueError(
                "timeout_seconds must be a positive number."
            ) from exc

        if value <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        return value

    # ---------------------------------------------------------
    # PATHS
    # ---------------------------------------------------------

    def _resolve_script(
        self,
        script,
    ):
        path = Path(script)

        if not path.is_absolute():
            path = (
                self.working_directory
                / path
            )

        return path.resolve()

    # ---------------------------------------------------------
    # SCRIPT EXECUTION
    # ---------------------------------------------------------

    def _run_script(
        self,
        script,
        cycle_name,
    ):
        script_path = self._resolve_script(
            script
        )

        command = [
            self.python_executable,
            str(script_path),
        ]

        try:
            completed = self.subprocess_runner(
                command,
                cwd=str(
                    self.working_directory
                ),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )

        except subprocess.TimeoutExpired as exc:
            return {
                "cycle": cycle_name,
                "status": "TIMEOUT",
                "success": False,
                "returncode": None,
                "script": str(script_path),
                "stdout": (
                    exc.stdout
                    if isinstance(exc.stdout, str)
                    else ""
                ),
                "stderr": (
                    exc.stderr
                    if isinstance(exc.stderr, str)
                    else ""
                ),
                "error": (
                    f"{cycle_name} cycle exceeded "
                    f"{self.timeout_seconds} seconds."
                ),
            }

        except Exception as exc:
            return {
                "cycle": cycle_name,
                "status": "ERROR",
                "success": False,
                "returncode": None,
                "script": str(script_path),
                "stdout": "",
                "stderr": "",
                "error": str(exc),
            }

        returncode = int(
            completed.returncode
        )

        success = (
            returncode == 0
        )

        return {
            "cycle": cycle_name,
            "status": (
                "COMPLETED"
                if success
                else "FAILED"
            ),
            "success": success,
            "returncode": returncode,
            "script": str(script_path),
            "stdout": (
                completed.stdout
                or ""
            ),
            "stderr": (
                completed.stderr
                or ""
            ),
            "error": (
                None
                if success
                else (
                    f"{cycle_name} cycle exited "
                    f"with code {returncode}."
                )
            ),
        }

    # ---------------------------------------------------------
    # PUBLIC CYCLES
    # ---------------------------------------------------------

    def run_opportunity_cycle(
        self,
    ):
        return self._run_script(
            self.opportunity_script,
            "OPPORTUNITY",
        )

    def run_monitoring_cycle(
        self,
    ):
        return self._run_script(
            self.monitoring_script,
            "MONITORING",
        )
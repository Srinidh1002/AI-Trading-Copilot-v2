import subprocess
import sys
from textwrap import dedent


FORBIDDEN_MODULES = (
    "pandas",
    "numpy",
    "scipy",
    "requests",
    "yfinance",
    "streamlit",
    "SmartApi",
    "smartapi",
)


def test_replay_fixture_has_no_heavy_runtime_imports():
    script = dedent(
        f"""
        import importlib
        import sys

        forbidden = {FORBIDDEN_MODULES!r}

        before = set(sys.modules)

        importlib.import_module("tests.fixtures.external_context")

        newly_loaded = set(sys.modules) - before

        violations = sorted(
            module
            for module in newly_loaded
            if any(
                module == forbidden_name
                or module.startswith(forbidden_name + ".")
                for forbidden_name in forbidden
            )
        )

        if violations:
            raise SystemExit(
                "P5-9 replay fixture loaded forbidden modules: "
                + ", ".join(violations)
            )
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=".",
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, (
        completed.stdout + completed.stderr
    )
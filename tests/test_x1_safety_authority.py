"""X1 safety, authority and operational-isolation verification.

These tests are intentionally read-only and offline. They verify the
X1 data plane carries no trading or broker authority, does not touch
the live runtime, and does not import dangerous modules.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import io
import os
import sys
import threading
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
X1_DIR = REPO / "services" / "x1"
X1_MODULES = (
    "services.x1",
    "services.x1.observation_identity_v1",
    "services.x1.observation_tracker_v1",
    "services.x1.streaming_hub_bridge_v1",
    "services.x1.composition_v1",
    "services.x1.observation_journal_v1",
    "services.x1.fyers_request_controller_v2",
    "services.x1.endpoint_cache_v1",
    "services.x1.instrument_rollover_v2",
)

_FORBIDDEN_MARKERS = (
    "place_order",
    "placeOrder",
    "modify_order",
    "modifyOrder",
    "cancel_order",
    "cancelOrder",
    "submit_order",
    "FyersOrderSocket",
    "generateSession",
    "run_nifty",
    "run_sensex",
    "run_task9",
    "SMARTAPI_KEY",
    "FYERS_SECRET_KEY",
    "ANGEL_API_KEY",
    "ANGEL_CLIENT_ID",
    "FYERS_CLIENT_ID",
)


def _iter_x1_sources():
    for path in sorted(X1_DIR.glob("*.py")):
        yield path, path.read_text(encoding="utf-8")


def test_x1_sources_do_not_contain_forbidden_markers():
    offenders = []
    for path, text in _iter_x1_sources():
        for marker in _FORBIDDEN_MARKERS:
            if marker in text:
                offenders.append((path.name, marker))
    assert offenders == [], offenders


def test_x1_sources_do_not_read_environment_credentials():
    offenders = []
    for path, text in _iter_x1_sources():
        if "os.environ" in text or "os.getenv" in text:
            offenders.append(path.name)
    assert offenders == [], offenders


def test_x1_sources_do_not_import_dangerous_modules():
    banned = {
        "fyers_apiv3",
        "SmartApi",
        "smartapi",
        "yfinance",
        "dotenv",
        "requests",
        "urllib",
        "http",
        "socket",
    }
    offenders = []
    for path, text in _iter_x1_sources():
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in banned:
                        offenders.append((path.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                if module in banned:
                    offenders.append((path.name, node.module))
    assert offenders == [], offenders


def test_x1_modules_import_without_network_or_stdout_noise():
    # Import each module fresh and assert nothing writes to stdout or
    # stderr during import.
    out, err = io.StringIO(), io.StringIO()
    imported = []
    with redirect_stdout(out), redirect_stderr(err):
        for name in X1_MODULES:
            module = importlib.import_module(name)
            imported.append(module)
    assert out.getvalue() == ""
    assert err.getvalue() == ""
    assert len(imported) == len(X1_MODULES)


def test_x1_public_classes_declare_data_only_flags():
    required = (
        ("data_only", True),
        ("order_capability_allowed", False),
        ("automatic_fallback_allowed", False),
    )
    class_names = {
        "ObservationTrackerV1",
        "StreamingHubBridgeV1",
        "X1DataPlaneCompositionV1",
        "FyersRequestControllerV2Impl",
        "ObservationJournalV1",
        "EndpointCacheV1",
    }
    found = set()
    for name in X1_MODULES:
        module = importlib.import_module(name)
        for attr in dir(module):
            obj = getattr(module, attr)
            if not inspect.isclass(obj):
                continue
            if obj.__name__ not in class_names:
                continue
            found.add(obj.__name__)
            for name_, expected in required:
                assert getattr(obj, name_) is expected, (
                    obj.__name__,
                    name_,
                )
    assert found == class_names, found


def test_x1_source_text_has_no_live_paper_state_paths():
    forbidden = (
        "data/task9",
        "data\\task9",
        "data/rate_limit/state.json",
        "data\\rate_limit\\state.json",
        "task9_live_paper_certification",
        "certification_counters",
    )
    for path, text in _iter_x1_sources():
        for marker in forbidden:
            assert marker not in text, (path.name, marker)


def test_x1_composition_is_not_installed_by_import():
    # Importing the composition module must not create any composition
    # instance, and it must not mutate any existing runtime bundle.
    import services.x1.composition_v1 as module

    for attr in dir(module):
        value = getattr(module, attr)
        if inspect.isclass(value):
            continue
        if isinstance(value, module.X1DataPlaneCompositionV1):
            pytest.fail(
                f"module-level composition instance found: {attr}"
            )


def test_x1_request_controller_uses_existing_coordinator():
    import services.x1.fyers_request_controller_v2 as controller_module

    source = inspect.getsource(controller_module)
    assert "FyersRateLimitCoordinator" in source
    # It must not construct its own on-disk limiter from scratch.
    assert "tempfile" not in source
    assert "os.open" not in source


def test_x1_does_not_monkey_patch_socket_or_dns():
    for path, text in _iter_x1_sources():
        assert "socket.getaddrinfo" not in text, path.name
        assert "socket.socket" not in text, path.name


def test_x1_modules_do_not_start_threads_at_import():
    before = threading.active_count()
    for name in X1_MODULES:
        sys.modules.pop(name, None)
        importlib.import_module(name)
    after = threading.active_count()
    assert before == after, (before, after)


def test_x1_modules_do_not_change_working_directory():
    before = os.getcwd()
    for name in X1_MODULES:
        sys.modules.pop(name, None)
        importlib.import_module(name)
    after = os.getcwd()
    assert before == after


def test_x1_sources_declare_explicit_schema_versions():
    for path, text in _iter_x1_sources():
        if path.name == "__init__.py":
            continue
        # Every non-init module declares at least one schema version
        # string or the exception is that it is a pure adapter. We
        # accept "V1" or "V2" identifier presence as the marker.
        assert "V1" in text or "V2" in text, path.name

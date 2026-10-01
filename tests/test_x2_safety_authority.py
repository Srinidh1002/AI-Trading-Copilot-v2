"""X2 safety, authority and operational-isolation verification.

Read-only and offline. Verifies the X2 package carries no trading or
broker authority, does not touch the live runtime, and does not import
dangerous modules.
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

REPO = Path(__file__).resolve().parents[1]
X2_DIR = REPO / "services" / "x2"
X2_MODULES = (
    "services.x2",
    "services.x2.constituent_universe_v1",
    "services.x2.constituent_influence_v1",
    "services.x2.weighted_breadth_v1",
    "services.x2.heatmap_v1",
    "services.x2.sector_strength_v1",
    "services.x2.relative_strength_v1",
    "services.x2.feature_manifest_v1",
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

_BANNED_IMPORT_TOPS = {
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


def _iter_x2_sources():
    for path in sorted(X2_DIR.glob("*.py")):
        yield path, path.read_text(encoding="utf-8")


def test_x2_sources_do_not_contain_forbidden_markers():
    offenders = []
    for path, text in _iter_x2_sources():
        for marker in _FORBIDDEN_MARKERS:
            if marker in text:
                offenders.append((path.name, marker))
    assert offenders == [], offenders


def test_x2_sources_do_not_read_environment_credentials():
    offenders = []
    for path, text in _iter_x2_sources():
        if "os.environ" in text or "os.getenv" in text:
            offenders.append(path.name)
    assert offenders == [], offenders


def test_x2_sources_do_not_import_dangerous_modules():
    offenders = []
    for path, text in _iter_x2_sources():
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in _BANNED_IMPORT_TOPS:
                        offenders.append((path.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                if module in _BANNED_IMPORT_TOPS:
                    offenders.append((path.name, node.module))
    assert offenders == [], offenders


def test_x2_modules_import_without_noise():
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        for name in X2_MODULES:
            sys.modules.pop(name, None)
            importlib.import_module(name)
    assert out.getvalue() == ""
    assert err.getvalue() == ""


def test_x2_source_text_has_no_live_state_paths():
    forbidden = (
        "data/task9",
        "data\\task9",
        "data/rate_limit/state.json",
        "data\\rate_limit\\state.json",
        "task9_live_paper_certification",
        "certification_counters",
        "data/paper_trades",
        "data\\paper_trades",
    )
    for path, text in _iter_x2_sources():
        for marker in forbidden:
            assert marker not in text, (path.name, marker)


def test_x2_does_not_monkey_patch_socket_or_dns():
    for path, text in _iter_x2_sources():
        assert "socket.getaddrinfo" not in text, path.name
        assert "socket.socket" not in text, path.name


def test_x2_modules_do_not_start_threads_at_import():
    before = threading.active_count()
    for name in X2_MODULES:
        sys.modules.pop(name, None)
        importlib.import_module(name)
    after = threading.active_count()
    assert before == after, (before, after)


def test_x2_modules_do_not_change_working_directory():
    before = os.getcwd()
    for name in X2_MODULES:
        sys.modules.pop(name, None)
        importlib.import_module(name)
    after = os.getcwd()
    assert before == after


def test_mcx_markets_are_explicitly_not_applicable_in_manifest():
    from services.x2.feature_manifest_v1 import (
        DEFAULT_X2_FEATURE_MANIFEST_V1,
        NOT_APPLICABLE_MARKETS_V1,
        SUPPORTED_MARKETS_V1,
    )

    for d in DEFAULT_X2_FEATURE_MANIFEST_V1.descriptors:
        for mkt in d.markets:
            assert mkt in SUPPORTED_MARKETS_V1
            assert mkt not in NOT_APPLICABLE_MARKETS_V1
    assert NOT_APPLICABLE_MARKETS_V1 == frozenset(
        {"CRUDEOILM", "GOLDM", "NATGASMINI"}
    )


def test_x2_does_not_alter_frozen_brain_registry():
    # Snapshot the frozen V1 registry before and after X2 imports.
    from services.brain.analyzer_registry_v1 import (
        DEFAULT_ANALYZER_REGISTRY_V1,
    )

    before = tuple(
        d.analyzer_id for d in DEFAULT_ANALYZER_REGISTRY_V1.descriptors
    )
    for name in X2_MODULES:
        sys.modules.pop(name, None)
        importlib.import_module(name)
    after = tuple(
        d.analyzer_id for d in DEFAULT_ANALYZER_REGISTRY_V1.descriptors
    )
    assert before == after


def test_x2_public_classes_have_data_only_flags_where_applicable():
    import dataclasses

    from services.x2 import constituent_influence_v1 as ci
    from services.x2 import feature_manifest_v1 as fm
    from services.x2 import heatmap_v1 as hm
    from services.x2 import relative_strength_v1 as rs
    from services.x2 import sector_strength_v1 as ss
    from services.x2 import weighted_breadth_v1 as wb

    authority_names = (
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
    )
    modules = (ci, hm, rs, ss, wb, fm)
    for mod in modules:
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if not inspect.isclass(obj):
                continue
            if obj.__module__ != mod.__name__:
                continue
            if dataclasses.is_dataclass(obj):
                fields = obj.__dataclass_fields__
                for name in authority_names:
                    if name not in fields:
                        continue
                    default = fields[name].default
                    assert default is False, (
                        obj.__name__,
                        name,
                        default,
                    )
            else:
                for name in authority_names:
                    value = getattr(obj, name, False)
                    assert value is False, (obj.__name__, name)

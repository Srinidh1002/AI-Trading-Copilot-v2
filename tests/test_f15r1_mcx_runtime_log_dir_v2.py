"""Phase 15 — MCX runtime log-directory creation tests.

The runtime builder is the boundary that guarantees the FYERS SDK
log directory exists before the SDK is constructed. Ad-hoc MCX scripts
that bypass login() rely on this guarantee.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from mcx import mcx_fyers_runtime_v2 as rmod  # noqa: E402
from mcx.mcx_fyers_runtime_v2 import build_mcx_fyers_runtime_v2  # noqa: E402


class _FakeBridge:
    identity = object()
    data = object()


@pytest.fixture
def patched_composition(monkeypatch):
    """Replace the runtime composition tail so tests only exercise mkdir."""
    monkeypatch.setattr(rmod, "build_mcx_fyers_bridge_v2", lambda **kw: _FakeBridge())
    monkeypatch.setattr(rmod, "MCXFyersNativeChainV2", lambda **kw: object())
    monkeypatch.setattr(rmod, "MCXFyersRuntimeV2", lambda **kw: object())


def test_runtime_builder_creates_log_dir(tmp_path, patched_composition):
    observed = {}

    def fake_builder(*, client_id, access_token, log_path):
        observed["log_path"] = log_path
        observed["dir_exists"] = Path(log_path).is_dir()
        return object()

    log_dir = tmp_path / "logs" / "mcx_test"
    assert not log_dir.exists()

    build_mcx_fyers_runtime_v2(
        client_id="X",
        access_token="Y",
        log_path=str(log_dir),
        master_store=object(),
        client_builder=fake_builder,
    )

    assert log_dir.is_dir()
    assert observed["log_path"] == str(log_dir)
    assert observed["dir_exists"] is True


def test_runtime_builder_creates_nested_log_dir(tmp_path, patched_composition):
    observed = {}

    def fake_builder(*, client_id, access_token, log_path):
        observed["dir_exists"] = Path(log_path).is_dir()
        return object()

    log_dir = tmp_path / "a" / "b" / "c" / "d"
    assert not log_dir.exists()

    build_mcx_fyers_runtime_v2(
        client_id="X",
        access_token="Y",
        log_path=str(log_dir),
        master_store=object(),
        client_builder=fake_builder,
    )

    assert log_dir.is_dir()
    assert observed["dir_exists"] is True


def test_runtime_builder_idempotent_when_dir_exists(tmp_path, patched_composition):
    log_dir = tmp_path / "logs" / "existing"
    log_dir.mkdir(parents=True)
    marker = log_dir / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    build_mcx_fyers_runtime_v2(
        client_id="X",
        access_token="Y",
        log_path=str(log_dir),
        master_store=object(),
        client_builder=lambda **kw: object(),
    )

    assert log_dir.is_dir()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_runtime_builder_rejects_file_as_log_dir(tmp_path, patched_composition):
    collide = tmp_path / "logs"
    collide.write_text("I am a file", encoding="utf-8")

    with pytest.raises(FileExistsError):
        build_mcx_fyers_runtime_v2(
            client_id="X",
            access_token="Y",
            log_path=str(collide),
            master_store=object(),
            client_builder=lambda **kw: object(),
        )


def test_runtime_builder_rejects_empty_log_path():
    with pytest.raises(Exception):
        build_mcx_fyers_runtime_v2(
            client_id="X",
            access_token="Y",
            log_path="",
            master_store=object(),
            client_builder=lambda **kw: object(),
        )

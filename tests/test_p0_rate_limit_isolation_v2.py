"""R2-3 — live rate-limit state must never be touched by an offline test."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src import rate_limiter  # noqa: E402

LIVE_STATE = REPO / "data" / "rate_limit" / "state.json"


def _hash_file(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "MISSING"


def test_env_var_override_is_set_by_conftest():
    override = os.environ.get("FYERS_RATE_LIMIT_STATE_PATH")
    assert override, "conftest must set FYERS_RATE_LIMIT_STATE_PATH"
    assert "pytest_rate_limit_isolated_" in override


def test_default_state_path_honors_env_var():
    p = rate_limiter._default_state_path()
    override = os.environ.get("FYERS_RATE_LIMIT_STATE_PATH")
    assert str(p) == override


def test_default_coordinator_uses_temp_path():
    """A coordinator built with no state_path must use the temp file."""
    c = rate_limiter.FyersRateLimitCoordinator()
    override = os.environ.get("FYERS_RATE_LIMIT_STATE_PATH")
    assert str(c._state_path) == str(Path(override).resolve())
    assert c._state_path != LIVE_STATE


def test_a_permit_does_not_touch_live_state(tmp_path):
    """Consuming a permit through the default-constructed coordinator must
    not change data/rate_limit/state.json."""
    before = _hash_file(LIVE_STATE)
    before_size = LIVE_STATE.stat().st_size if LIVE_STATE.exists() else -1

    c = rate_limiter.FyersRateLimitCoordinator(worker_name="test_isolation")
    c.wait_if_needed("probe")

    after = _hash_file(LIVE_STATE)
    after_size = LIVE_STATE.stat().st_size if LIVE_STATE.exists() else -1
    assert after == before, "live rate-limit state changed during test"
    assert after_size == before_size


def test_live_guard_file_not_created(tmp_path):
    """The .lock guard file in data/rate_limit/ must not appear."""
    live_lock = REPO / "data" / "rate_limit" / "state.json.lock"
    c = rate_limiter.FyersRateLimitCoordinator(worker_name="test_isolation2")
    c.wait_if_needed("probe")
    assert not live_lock.exists() or live_lock.stat().st_size == 0, (
        "live guard file should not have been created or grown"
    )

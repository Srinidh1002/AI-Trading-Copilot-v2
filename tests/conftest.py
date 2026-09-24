"""Global test isolation.

Every test session sets FYERS_RATE_LIMIT_STATE_PATH to a temp file so
that any offline test that constructs a FyersRateLimitCoordinator (even
without passing state_path) writes permits to a temp location, never to
data/rate_limit/state.json in the live repository.

The env var is the belt-and-braces layer. Tests that care about
isolation should also pass an explicit state_path.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


@pytest.fixture(scope="session", autouse=True)
def _isolate_live_rate_limit_state():
    """Redirect the default limiter path to a session-scoped temp file."""
    tmp = Path(tempfile.mkdtemp(prefix="pytest_rate_limit_isolated_"))
    state = tmp / "state.json"
    prev = os.environ.get("FYERS_RATE_LIMIT_STATE_PATH")
    os.environ["FYERS_RATE_LIMIT_STATE_PATH"] = str(state)
    yield state
    # Restore on session end
    if prev is None:
        os.environ.pop("FYERS_RATE_LIMIT_STATE_PATH", None)
    else:
        os.environ["FYERS_RATE_LIMIT_STATE_PATH"] = prev

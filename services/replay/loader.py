"""JSON-only loading for offline replay fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from services.contracts.replay_fixture_v1 import ReplayFixtureV1


def load_replay_fixture(path: str | Path) -> ReplayFixtureV1:
    """Load a saved fixture without acquiring market data or mutating state."""
    with Path(path).open("r", encoding="utf-8") as fixture_file:
        return ReplayFixtureV1.from_dict(json.load(fixture_file))

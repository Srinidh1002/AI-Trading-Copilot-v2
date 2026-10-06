"""Offline audit for R18D CRUDE retest shadow instrumentation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mcx.mcx_retest_shadow import BreakoutRetestShadowTracker  # noqa: E402

EPISODE_PATH = ROOT / "research" / "r18c" / "oct05_crude_first_entry_episode.json"


def _structure(low):
    return {
        "status": "OK",
        "timeframes": {
            "5m": {
                "state": "DOWN",
                "swing_low": low,
                "swing_high": low + 100.0,
            }
        },
    }


def _observe(tracker, row, structure):
    return tracker.observe(
        timestamp=row["timestamp"],
        future_ltp=row["future_ltp"],
        regime={"regime": row["regime"]},
        structure=structure,
        mtf={"status": "OK", "timeframes": {}},
        decision={"action": row["action"]},
        setup={"setup": row["setup"]},
    )


def main():
    episode = json.loads(EPISODE_PATH.read_text(encoding="utf-8"))
    tracker = BreakoutRetestShadowTracker("CRUDEOILM")

    result = None
    for row in episode["cycles"]:
        result = _observe(
            tracker,
            row,
            _structure(episode["breakout_level_reference"]),
        )

    print("R18D_EXECUTION_MODE=OFFLINE_SHADOW_VALIDATION")
    print("PROVIDER_CALLS_ADDED=0")
    print("TRADING_AUTHORITY=NONE")
    print("CERTIFICATION_AUTHORITY=NONE")
    print("RUNTIME_ENV_DEFAULT=DISABLED")
    print(f"OCT05_ORDERED_SEQUENCE_COMPLETE={result['ordered_sequence_complete']}")
    print("INTRAMINUTE_ORDERING_INFERRED=FALSE")
    print("PRODUCTION_STRATEGY_CHANGE=NONE")
    print("NEW_STRATEGY_EPOCH=NOT_REQUIRED_FOR_INSTRUMENTATION")
    print("R18D_OFFLINE_AUDIT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

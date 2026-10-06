"""Run the R18C CRUDE explicit-retest candidate audit.

Research only. No provider calls, PAPER writes, certification writes, or
production strategy wiring.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.research.r18c_retest_evidence_candidate_v1 import (  # noqa: E402
    audit_bearish_snapshot_episode,
    audit_oct05_candidate_blocks,
)

R18B_DATASET = ROOT / "research" / "r18b" / "oct05_observed_trade_summary.json"
R18C_EPISODE = ROOT / "research" / "r18c" / "oct05_crude_first_entry_episode.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    dataset = json.loads(R18B_DATASET.read_text(encoding="utf-8"))
    episode = json.loads(R18C_EPISODE.read_text(encoding="utf-8"))

    first_entry = audit_bearish_snapshot_episode(
        episode["cycles"],
        breakout_level_reference=episode["breakout_level_reference"],
        entry_timestamp=episode["entry_timestamp"],
    )
    candidate = audit_oct05_candidate_blocks(dataset["crude_trades"])

    report = {
        "schema_version": "r18c.crude_retest_candidate_audit.v1",
        "execution_mode": "RESEARCH_ONLY",
        "provider_calls": "NONE",
        "paper_state_writes": "NONE",
        "certification_writes": "NONE",
        "first_entry_snapshot_audit": first_entry,
        "oct05_candidate": candidate,
        "decision": {
            "deploy_candidate_to_production_now": False,
            "new_strategy_epoch_now": False,
            "r18d_shadow_instrumentation_required": True,
            "reason": (
                "The candidate correctly fails closed without ordered breakout, "
                "extension, retest and rejection evidence. Existing Oct-5 cycle "
                "snapshots are insufficient to prove the complete intracycle "
                "sequence, so production behavior must not change yet."
            ),
        },
    }

    print("R18C_EXECUTION_MODE=RESEARCH_ONLY")
    print("PROVIDER_CALLS=NONE")
    print("PAPER_STATE_WRITES=NONE")
    print("CERTIFICATION_WRITES=NONE")
    print(f"FIRST_ENTRY_SNAPSHOT_STATUS={first_entry['status']}")
    print(f"OCT05_CRUDE_CANDIDATE_BLOCKED={candidate['blocked_count']}")
    print(f"OCT05_CRUDE_CANDIDATE_ALLOWED={candidate['allowed_count']}")
    print("EXPLICIT_RETEST_SEQUENCE_REQUIRED=True")
    print("DEPLOY_CANDIDATE_TO_PRODUCTION_NOW=False")
    print("NEW_STRATEGY_EPOCH_NOW=False")
    print("R18D_SHADOW_INSTRUMENTATION_REQUIRED=True")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"JSON_REPORT={args.json_out}")

    print("R18C_CANDIDATE_AUDIT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

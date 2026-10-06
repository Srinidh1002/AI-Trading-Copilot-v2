"""Run the R18B Oct-5 offline shadow analysis.

No provider calls. No PAPER state writes. No certification writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.research.r18b_strategy_shadow_v1 import analyze_dataset  # noqa: E402

DEFAULT_DATASET = ROOT / "research" / "r18b" / "oct05_observed_trade_summary.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    report = analyze_dataset(dataset)

    print("R18B_EXECUTION_MODE=RESEARCH_ONLY")
    print("PROVIDER_CALLS=NONE")
    print("PAPER_STATE_WRITES=NONE")
    print("CERTIFICATION_WRITES=NONE")
    print(f"INDEX_OBSERVED_TRADES={report['index']['observed_trade_count']}")
    print(f"INDEX_OBSERVED_LOSSES={report['index']['observed_losses']}")
    print(f"INDEX_CHOPPY_TRADES={report['index']['choppy_trade_count']}")
    print(f"INDEX_CHOPPY_LOSSES={report['index']['choppy_loss_count']}")
    print(f"INDEX_CHOPPY_OBSERVED_NET_PNL={report['index']['choppy_observed_net_pnl']:.2f}")
    print(f"CRUDE_OBSERVED_TRADES={report['crude']['observed_trade_count']}")
    print(
        "CRUDE_BREAKOUT_RETEST_MISSING_EXPLICIT_EVIDENCE="
        f"{report['crude']['breakout_retest_missing_explicit_retest_evidence']}"
    )

    for row in report["index"]["pre_t1_threshold_observations"]:
        print(
            "PRE_T1_ARM "
            f"threshold={row['threshold_pct']:.1f} "
            f"count={row['armed_count']} wins={row['armed_wins']} "
            f"losses={row['armed_losses']}"
        )

    for row in report["crude"]["cooldown_observations"]:
        print(
            "CRUDE_COOLDOWN_OBSERVED "
            f"minutes={row['cooldown_minutes']} "
            f"inside_window={row['observed_entries_inside_window']} "
            f"trade_ids={','.join(row['trade_ids']) or '-'}"
        )

    recommendation = report["recommendation"]
    print(
        "PROMOTE_EXPLICIT_RETEST_CANDIDATE="
        f"{recommendation['promote_explicit_breakout_retest_evidence_requirement_to_candidate']}"
    )
    deploy_index_change = (
        recommendation["deploy_index_choppy_veto_now"]
        or recommendation["deploy_pre_t1_profit_lock_now"]
    )
    print(f"DEPLOY_INDEX_STRATEGY_CHANGE_NOW={deploy_index_change}")
    print(f"DEPLOY_FIXED_CRUDE_COOLDOWN_NOW={recommendation['deploy_fixed_crude_cooldown_now']}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"JSON_REPORT={args.json_out}")

    print("R18B_SHADOW_ANALYSIS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

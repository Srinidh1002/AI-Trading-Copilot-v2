"""Diagnostic-only Task 9.112 persisted-evidence probe.

This intentionally does not start Task 9, contact a provider, or mutate any
persisted evidence.  It reports the first precise fail-closed rehydration
boundary when the nested graph lacks canonical inverse serializers.
"""

from pathlib import Path
import hashlib
import subprocess
from dataclasses import replace

from tests.support.task9_evidence_rehydration import (
    RehydrationIncomplete,
    rehydrate_composition_policy,
    rehydrate_market_analysis_composition,
    _snapshot,
    rehydrate_task9_evaluation_snapshot,
)
from services.analysis.market_analysis_candidate_composer import compose_market_analysis_candidate


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data" / "task9" / "live-decision-audit.json"
OBSERVATIONS = (
    "task9-nifty-2026-08-24T14:16:19+05:30",
    "task9-sensex-2026-08-26T12:05:02+05:30",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    print("=" * 60)
    print("TASK 9.113 — COMPLETE COMPOSITION-GRAPH REHYDRATION RESULT")
    print("=" * 60)
    evidence_files = (
        ROOT / "data" / "task9" / "prediction-ledger.json",
        ROOT / "data" / "task9" / "live-decision-audit.json",
    )
    before = {path: _sha256(path) for path in evidence_files}
    for observation_id in OBSERVATIONS:
        print(f"\n{observation_id}")
        try:
            composition = rehydrate_task9_evaluation_snapshot(
                audit_path=AUDIT, observation_id=observation_id
            )
            snapshot = _snapshot(audit_path=AUDIT, observation_id=observation_id)
            policy = rehydrate_composition_policy(snapshot["policy"], observation_id=observation_id)
            result = compose_market_analysis_candidate(composition, policy)
        except RehydrationIncomplete as exc:
            print(f"status=INCOMPLETE reason={exc}")
        else:
            print("status=REHYDRATED")
            print(f"composer=REACHED eligibility={result.eligibility} direction={result.direction} confidence={result.confidence} score={result.score}")
            print(f"blockers={result.blockers}")
            if composition.regime is not None:
                counter_regime = replace(composition.regime, entry_suitability="SUITABLE")
                changed = [
                    field.name for field in __import__("dataclasses").fields(composition.regime)
                    if getattr(composition.regime, field.name) != getattr(counter_regime, field.name)
                ]
                if changed != ["entry_suitability"]:
                    raise RuntimeError(f"REHYDRATION_MUTATION_ERROR: {changed}")
                counter = compose_market_analysis_candidate(
                    replace(composition, regime=counter_regime), policy
                )
                print(f"counterfactual eligibility={counter.eligibility} direction={counter.direction} confidence={counter.confidence} score={counter.score}")
    print("COUNTERFACTUAL=NOT_RUN")
    print("PARENT=NOT_REACHED")
    print("PLANNER=NOT_REACHED")
    print("COUNTABLE=NOT_PROVEN")
    after = {path: _sha256(path) for path in evidence_files}
    print(f"PERSISTED_EVIDENCE_UNCHANGED={'PASS' if before == after else 'FAIL'}")
    diff = subprocess.run(
        ["git", "diff", "--", "data/task9"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"GIT_DIFF_DATA_TASK9={'CLEAN' if not diff.stdout else 'CHANGED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

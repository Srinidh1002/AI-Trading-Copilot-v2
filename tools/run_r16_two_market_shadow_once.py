#!/usr/bin/env python3
"""Run exactly one FYERS-backed R16 NIFTY/SENSEX SHADOW parent cycle.

Observation only:
- no PAPER entry
- no position/state mutation
- no broker order capability
- no certification counter mutation
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.broker.fyers_auth_v2 import (
    assert_fyers_token_current_v2,
    load_canonical_credentials_v2,
)
from services.broker.fyers_provider_runtime_v2 import (
    check_fyers_provider_health_v2,
)
from services.broker.fyers_sdk_data_client_v2 import (
    build_fyers_data_client_v2,
)
from services.paper_orchestration.fyers_master_readiness_v2 import (
    audit_required_master_cache,
)
from services.paper_orchestration.r16_fyers_shadow_composition_v1 import (
    build_r16_fyers_shadow_readers_v1,
)
from services.paper_orchestration.r16_two_market_shadow_source_v1 import (
    R16TwoMarketShadowSourceV1,
)


def _safe_candidate(candidate):
    if candidate is None:
        return None
    return {
        "candidate_id": candidate.candidate_id,
        "market": [
            candidate.underlying_symbol,
            candidate.exchange,
        ],
        "market_timestamp": candidate.market_timestamp.isoformat(),
        "direction": candidate.direction,
        "eligibility": candidate.eligibility,
        "confidence": candidate.confidence,
        "score": candidate.score,
        "blockers": list(candidate.blockers),
        "warnings": list(candidate.warnings),
        "contradictions": list(candidate.contradictions),
        "reasons": list(candidate.reasons),
    }


def _decision_payload(result):
    decision = result.decision
    return {
        "schema_version": "r16_two_market_shadow_report.v1",
        "mode": result.mode,
        "execution_mode": result.execution_mode,
        "live_execution_eligible": result.live_execution_eligible,
        "broker_order_submission": result.broker_order_submission,
        "parent_cycle_id": decision.parent_cycle_id,
        "decision_result_id": decision.decision_result_id,
        "requested_at": decision.requested_at.isoformat(),
        "completed_at": decision.completed_at.isoformat(),
        "decision": decision.decision,
        "selected_market": (
            list(decision.selected_market)
            if decision.selected_market is not None
            else None
        ),
        "selected_candidate_id": decision.selected_candidate_id,
        "timestamp_skew_seconds": decision.timestamp_skew_seconds,
        "blockers": list(decision.blockers),
        "warnings": list(decision.warnings),
        "entries": [
            {
                "market": [
                    entry.child.underlying_symbol,
                    entry.child.exchange,
                ],
                "terminal_status": entry.child.terminal_status,
                "failure_reason": entry.child.failure_reason,
                "eligible_for_comparison": entry.eligible_for_comparison,
                "rank_value": entry.rank_value,
                "outcome_reason": entry.outcome_reason,
                "rationale": list(entry.rationale),
                "candidate": _safe_candidate(entry.child.candidate),
            }
            for entry in decision.entries
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--instrument-file",
        default="data/instruments.json",
    )
    parser.add_argument(
        "--log-dir",
        default="logs/r16_fyers_shadow",
    )
    parser.add_argument("--capital", type=float, default=100000.0)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    env_file = Path(args.env_file)
    if not env_file.is_absolute():
        env_file = root / env_file
    instrument_file = Path(args.instrument_file)
    if not instrument_file.is_absolute():
        instrument_file = root / instrument_file
    log_dir = Path(args.log_dir)
    if not log_dir.is_absolute():
        log_dir = root / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    readiness = audit_required_master_cache(
        repo_root=root,
        markets=("NIFTY", "SENSEX"),
    )
    if not all(ok for ok, _reason in readiness.values()):
        print("R16_SHADOW_PREFLIGHT=HOLD")
        for market, (ok, reason) in readiness.items():
            print(
                f"MASTER[{market}]="
                f"{'PASS' if ok else 'HOLD'}:{reason}"
            )
        return 2

    credentials = load_canonical_credentials_v2(
        str(env_file)
    )
    assert_fyers_token_current_v2(
        credentials.access_token
    )

    client = build_fyers_data_client_v2(
        client_id=credentials.app_id,
        access_token=credentials.access_token,
        log_path=str(log_dir),
    )

    health = check_fyers_provider_health_v2(client)
    if not health.ok:
        print(
            "R16_SHADOW_PREFLIGHT=HOLD:"
            f"{health.reason_code}"
        )
        return 3

    rows = json.loads(
        instrument_file.read_text(encoding="utf-8-sig")
    )
    if not isinstance(rows, list):
        raise ValueError("instrument file must contain a list")

    readers = build_r16_fyers_shadow_readers_v1(
        data_client=client,
        instrument_rows=rows,
        legacy_instrument_path=instrument_file,
        available_capital=args.capital,
    )
    source = R16TwoMarketShadowSourceV1(
        readers=readers,
        clock=lambda: __import__(
            "datetime"
        ).datetime.now(
            __import__("datetime").timezone.utc
        ),
    )

    result = source.run_shadow_cycle()
    payload = _decision_payload(result)

    text = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )

    if args.output:
        target = Path(args.output)
        if not target.is_absolute():
            target = root / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
        print(f"REPORT={target}")
    else:
        print(text)

    print("R16_SHADOW_CYCLE=COMPLETE")
    print(f"DECISION={payload['decision']}")
    print(
        "SELECTED_MARKET="
        + (
            payload["selected_market"][0]
            if payload["selected_market"]
            else "NONE"
        )
    )
    print("EXECUTION_MODE=PAPER")
    print("PAPER_ENTRY_AUTHORITY=FALSE")
    print("BROKER_ORDER_SUBMISSION=FALSE")
    print("LIVE_EXECUTION=FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

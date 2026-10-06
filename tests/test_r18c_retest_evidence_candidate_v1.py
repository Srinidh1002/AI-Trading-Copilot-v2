from __future__ import annotations

import json
from pathlib import Path

from services.research.r18c_retest_evidence_candidate_v1 import (
    audit_bearish_snapshot_episode,
    audit_oct05_candidate_blocks,
    evaluate_breakout_retest_candidate,
    validate_explicit_retest_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
R18B_DATASET = ROOT / "research" / "r18b" / "oct05_observed_trade_summary.json"
R18C_EPISODE = ROOT / "research" / "r18c" / "oct05_crude_first_entry_episode.json"


def _ordered_evidence():
    return {
        "breakout_observed": True,
        "extension_observed": True,
        "retest_observed": True,
        "rejection_observed": True,
        "breakout_at": "2026-10-05T18:40:00",
        "extension_at": "2026-10-05T18:41:00",
        "retest_at": "2026-10-05T18:42:00",
        "rejection_at": "2026-10-05T18:43:00",
    }


def test_explicit_retest_contract_accepts_only_ordered_complete_evidence():
    result = validate_explicit_retest_evidence(_ordered_evidence())

    assert result["confirmed"] is True
    assert result["reason"] == "EXPLICIT_BREAKOUT_RETEST_CONFIRMED"


def test_missing_retest_event_fails_closed():
    evidence = _ordered_evidence()
    evidence["retest_observed"] = False

    result = evaluate_breakout_retest_candidate(
        regime="BREAKOUT_DOWN",
        mtf_aligned=True,
        evidence=evidence,
    )

    assert result["allow"] is False
    assert result["reason"] == "RETEST_EVENT_MISSING"
    assert result["evidence_validation"]["missing_events"] == ["retest_observed"]


def test_out_of_order_events_fail_closed():
    evidence = _ordered_evidence()
    evidence["retest_at"] = "2026-10-05T18:44:00"
    evidence["rejection_at"] = "2026-10-05T18:43:00"

    result = evaluate_breakout_retest_candidate(
        regime="BREAKOUT_DOWN",
        mtf_aligned=True,
        evidence=evidence,
    )

    assert result["allow"] is False
    assert result["reason"] == "RETEST_EVENT_ORDER_INVALID"


def test_wrong_regime_or_alignment_fails_closed_before_evidence():
    assert (
        evaluate_breakout_retest_candidate(
            regime="RANGE",
            mtf_aligned=True,
            evidence=_ordered_evidence(),
        )["reason"]
        == "NOT_BREAKOUT_REGIME"
    )

    assert (
        evaluate_breakout_retest_candidate(
            regime="BREAKOUT_DOWN",
            mtf_aligned=False,
            evidence=_ordered_evidence(),
        )["reason"]
        == "MTF_NOT_ALIGNED"
    )


def test_oct05_first_entry_has_no_retest_return_visible_in_cycle_snapshots():
    episode = json.loads(R18C_EPISODE.read_text(encoding="utf-8"))

    result = audit_bearish_snapshot_episode(
        episode["cycles"],
        breakout_level_reference=episode["breakout_level_reference"],
        entry_timestamp=episode["entry_timestamp"],
    )

    assert result["status"] == "NO_RETEST_RETURN_VISIBLE_IN_SNAPSHOTS"
    assert result["breakout_timestamp"] == "2026-10-05T18:40:20"
    assert result["breakout_price"] == 8632.0
    assert result["lowest_post_breakout_price"] == 8617.0
    assert result["returned_toward_level"] is False
    assert result["causal_counterfactual_valid"] is False


def test_synthetic_episode_can_show_return_toward_breakout_level():
    cycles = [
        {
            "timestamp": "2026-10-05T18:39:00",
            "future_ltp": 100.0,
            "regime": "RANGE",
        },
        {
            "timestamp": "2026-10-05T18:40:00",
            "future_ltp": 99.0,
            "regime": "BREAKOUT_DOWN",
        },
        {
            "timestamp": "2026-10-05T18:41:00",
            "future_ltp": 96.0,
            "regime": "BREAKOUT_DOWN",
        },
        {
            "timestamp": "2026-10-05T18:42:00",
            "future_ltp": 98.5,
            "regime": "BREAKOUT_DOWN",
        },
        {
            "timestamp": "2026-10-05T18:43:00",
            "future_ltp": 95.0,
            "regime": "BREAKOUT_DOWN",
        },
    ]

    result = audit_bearish_snapshot_episode(
        cycles,
        breakout_level_reference=100.0,
        entry_timestamp="2026-10-05T18:43:00",
    )

    assert result["status"] == "RETEST_RETURN_VISIBLE_IN_SNAPSHOTS"
    assert result["returned_toward_level"] is True
    assert result["return_timestamp"] == "2026-10-05T18:42:00"


def test_all_three_oct05_crude_trades_fail_closed_without_explicit_event_evidence():
    dataset = json.loads(R18B_DATASET.read_text(encoding="utf-8"))

    result = audit_oct05_candidate_blocks(dataset["crude_trades"])

    assert result["trade_count"] == 3
    assert result["allowed_count"] == 0
    assert result["blocked_count"] == 3
    assert result["causal_counterfactual_valid"] is False
    assert {row["reason"] for row in result["results"]} == {"RETEST_EVIDENCE_MISSING"}


def test_current_production_classifier_and_r18c_candidate_intentionally_differ():
    from mcx.mcx_setup import classify

    current = classify(
        {"action": "BUY_PUT"},
        {"regime": "BREAKOUT_DOWN"},
        {"overall_structure": "BEARISH", "vwap_position": "BELOW"},
        {
            "timeframes": {
                "5m": {"status": "OK", "trend": "DOWN"},
                "15m": {"status": "OK", "trend": "DOWN"},
                "30m": {"status": "OK", "trend": "DOWN"},
            }
        },
    )

    candidate = evaluate_breakout_retest_candidate(
        regime="BREAKOUT_DOWN",
        mtf_aligned=True,
        evidence=None,
    )

    assert current["setup"] == "BREAKOUT_RETEST"
    assert current["blocked"] is False
    assert candidate["allow"] is False
    assert candidate["reason"] == "RETEST_EVIDENCE_MISSING"

from __future__ import annotations

import json
from pathlib import Path

from services.research.r18b_strategy_shadow_v1 import (
    analyze_dataset,
    analyze_index_observations,
    shadow_breakout_retest_gate,
)

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "research" / "r18b" / "oct05_observed_trade_summary.json"


def _dataset():
    return json.loads(DATASET.read_text(encoding="utf-8"))


def test_oct05_observed_counts_and_pnl_are_stable():
    report = analyze_dataset(_dataset())

    assert report["execution_mode"] == "RESEARCH_ONLY"
    assert report["certification_countable"] is False

    assert report["index"]["observed_trade_count"] == 8
    assert report["index"]["observed_wins"] == 2
    assert report["index"]["observed_losses"] == 6
    assert report["index"]["observed_net_pnl"] == 89.52

    assert report["crude"]["observed_trade_count"] == 3
    assert report["crude"]["observed_losses"] == 3
    assert report["crude"]["observed_net_pnl"] == -1682.23


def test_choppy_observation_flags_four_losses_and_no_wins():
    report = analyze_index_observations(_dataset()["index_trades"])

    assert report["choppy_trade_count"] == 4
    assert report["choppy_loss_count"] == 4
    assert report["choppy_win_count"] == 0
    assert report["choppy_observed_net_pnl"] == -2414.54
    assert report["causal_counterfactual_valid"] is False


def test_pre_t1_threshold_scan_does_not_claim_alternate_pnl():
    report = analyze_index_observations(_dataset()["index_trades"])
    rows = {
        row["threshold_pct"]: row
        for row in report["pre_t1_threshold_observations"]
    }

    assert rows[8.0]["armed_count"] == 6
    assert rows[8.0]["armed_losses"] == 4
    assert rows[10.0]["armed_count"] == 4
    assert rows[10.0]["armed_losses"] == 2
    assert rows[12.0]["armed_count"] == 3
    assert rows[12.0]["armed_losses"] == 1
    assert rows[15.0]["armed_count"] == 2
    assert rows[15.0]["armed_losses"] == 0
    assert report["causal_counterfactual_valid"] is False


def test_crude_retest_and_reentry_observations_are_stable():
    report = analyze_dataset(_dataset())["crude"]

    assert report["breakout_retest_count"] == 3
    assert report["breakout_retest_missing_explicit_retest_evidence"] == 3
    assert len(report["observed_same_thesis_intervals"]) == 2

    first, second = report["observed_same_thesis_intervals"]
    assert first["same_thesis"] is True
    assert first["minutes_since_previous_exit"] == 2.033
    assert second["same_thesis"] is True
    assert second["minutes_since_previous_exit"] == 9.15

    cooldowns = {
        row["cooldown_minutes"]: row
        for row in report["cooldown_observations"]
    }
    assert cooldowns[5]["observed_entries_inside_window"] == 1
    assert cooldowns[10]["observed_entries_inside_window"] == 2
    assert cooldowns[15]["observed_entries_inside_window"] == 2
    assert report["causal_counterfactual_valid"] is False


def test_shadow_breakout_retest_requires_actual_retest_evidence():
    missing = shadow_breakout_retest_gate(
        regime="BREAKOUT_DOWN",
        mtf_aligned=True,
        explicit_retest_evidence=False,
    )
    assert missing == {
        "allow": False,
        "reason": "EXPLICIT_RETEST_EVIDENCE_MISSING",
    }

    confirmed = shadow_breakout_retest_gate(
        regime="BREAKOUT_DOWN",
        mtf_aligned=True,
        explicit_retest_evidence=True,
    )
    assert confirmed == {
        "allow": True,
        "reason": "BREAKOUT_RETEST_CONFIRMED",
    }


def test_r18b_recommendations_remain_shadow_only():
    recommendation = analyze_dataset(_dataset())["recommendation"]

    assert recommendation["deploy_index_choppy_veto_now"] is False
    assert recommendation["deploy_pre_t1_profit_lock_now"] is False
    assert recommendation["deploy_fixed_crude_cooldown_now"] is False
    assert (
        recommendation[
            "promote_explicit_breakout_retest_evidence_requirement_to_candidate"
        ]
        is True
    )


def test_current_production_breakout_retest_label_does_not_require_retest_event():
    from mcx.mcx_setup import classify

    decision = {"action": "BUY_PUT"}
    regime = {"regime": "BREAKOUT_DOWN"}
    structure = {"overall_structure": "BEARISH", "vwap_position": "BELOW"}
    mtf = {
        "timeframes": {
            "5m": {"status": "OK", "trend": "DOWN"},
            "15m": {"status": "OK", "trend": "DOWN"},
            "30m": {"status": "OK", "trend": "DOWN"},
        }
    }

    current = classify(decision, regime, structure, mtf)

    assert current["setup"] == "BREAKOUT_RETEST"
    assert current["blocked"] is False
    assert current["reasons"] == ["BREAKOUT_REGIME", "MTF_ALIGNED"]

    shadow = shadow_breakout_retest_gate(
        regime="BREAKOUT_DOWN",
        mtf_aligned=True,
        explicit_retest_evidence=False,
    )
    assert shadow["allow"] is False
    assert shadow["reason"] == "EXPLICIT_RETEST_EVIDENCE_MISSING"

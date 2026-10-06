from __future__ import annotations

import copy
import json
from pathlib import Path

from mcx.mcx_retest_shadow import BreakoutRetestShadowTracker
from services.research.r18c_retest_evidence_candidate_v1 import (
    validate_explicit_retest_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
R18C_EPISODE = ROOT / "research" / "r18c" / "oct05_crude_first_entry_episode.json"


def _mtf(ts, *, open_, high, low, close):
    return {
        "status": "OK",
        "timeframes": {
            "1m": {
                "status": "OK",
                "last_bar_timestamp": ts,
                "last_open": open_,
                "last_high": high,
                "last_low": low,
                "last_close": close,
            }
        },
    }


def _structure(low=100.0, high=110.0):
    return {
        "status": "OK",
        "timeframes": {
            "5m": {
                "state": "DOWN",
                "swing_low": low,
                "swing_high": high,
            }
        },
    }


def _observe(tracker, ts, price, regime, mtf, structure=None):
    return tracker.observe(
        timestamp=ts,
        future_ltp=price,
        regime={"regime": regime},
        structure=structure or _structure(),
        mtf=mtf,
        decision={"action": "BUY_PUT" if regime == "BREAKOUT_DOWN" else "NO_TRADE"},
        setup={"setup": "BREAKOUT_RETEST" if regime == "BREAKOUT_DOWN" else "NONE"},
    )


def test_shadow_tracker_adds_no_provider_or_trading_authority():
    source = (ROOT / "src" / "mcx" / "mcx_retest_shadow.py").read_text(encoding="utf-8")

    for forbidden in (
        "getCandleData(",
        "getMarketData(",
        "ltpData(",
        "optionchain(",
        "native_chain",
        "placeOrder(",
    ):
        assert forbidden not in source

    tracker = BreakoutRetestShadowTracker("CRUDEOILM")
    record = _observe(
        tracker,
        "2026-10-06T10:00:00+05:30",
        100.0,
        "RANGE",
        _mtf(
            "2026-10-06T10:00:00+05:30",
            open_=101.0,
            high=101.0,
            low=100.0,
            close=100.0,
        ),
    )

    assert record["provider_calls_added"] == 0
    assert record["trading_authority"] is False
    assert record["certification_countable"] is False


def test_distinct_minute_breakout_extension_retest_rejection_orders_correctly():
    tracker = BreakoutRetestShadowTracker("CRUDEOILM")

    _observe(
        tracker,
        "2026-10-06T10:00:00+05:30",
        100.0,
        "RANGE",
        _mtf(
            "2026-10-06T10:00:00+05:30",
            open_=101.0,
            high=101.0,
            low=100.0,
            close=100.0,
        ),
        _structure(low=100.0),
    )
    breakout = _observe(
        tracker,
        "2026-10-06T10:01:00+05:30",
        99.0,
        "BREAKOUT_DOWN",
        _mtf(
            "2026-10-06T10:01:00+05:30",
            open_=100.0,
            high=100.0,
            low=99.0,
            close=99.0,
        ),
        _structure(low=99.0),
    )
    extension = _observe(
        tracker,
        "2026-10-06T10:02:00+05:30",
        96.0,
        "BREAKOUT_DOWN",
        _mtf(
            "2026-10-06T10:02:00+05:30",
            open_=99.0,
            high=99.0,
            low=96.0,
            close=96.0,
        ),
    )
    retest = _observe(
        tracker,
        "2026-10-06T10:03:00+05:30",
        98.0,
        "BREAKOUT_DOWN",
        _mtf(
            "2026-10-06T10:03:00+05:30",
            open_=96.0,
            high=99.0,
            low=96.0,
            close=98.0,
        ),
    )
    rejection = _observe(
        tracker,
        "2026-10-06T10:04:00+05:30",
        95.0,
        "BREAKOUT_DOWN",
        _mtf(
            "2026-10-06T10:04:00+05:30",
            open_=98.0,
            high=98.0,
            low=95.0,
            close=95.0,
        ),
    )

    assert breakout["episode"]["breakout_reference"] == 100.0
    assert extension["episode"]["extension_observed"] is True
    assert retest["episode"]["retest_observed"] is True
    assert rejection["episode"]["rejection_observed"] is True
    assert rejection["ordered_sequence_complete"] is True

    evidence = rejection["explicit_retest_evidence_detail"]
    assert evidence["breakout_at"] == "2026-10-06T10:01:00+05:30"
    assert evidence["extension_at"] == "2026-10-06T10:02:00+05:30"
    assert evidence["retest_at"] == "2026-10-06T10:03:00+05:30"
    assert evidence["rejection_at"] == "2026-10-06T10:04:00+05:30"

    validation = validate_explicit_retest_evidence(evidence)
    assert validation["confirmed"] is True
    assert validation["reason"] == "EXPLICIT_BREAKOUT_RETEST_CONFIRMED"


def test_same_minute_bar_cannot_fabricate_ordered_sequence():
    tracker = BreakoutRetestShadowTracker("CRUDEOILM")

    _observe(
        tracker,
        "2026-10-06T10:00:10+05:30",
        100.0,
        "RANGE",
        _mtf(
            "2026-10-06T10:00:00+05:30",
            open_=101.0,
            high=101.0,
            low=100.0,
            close=100.0,
        ),
        _structure(low=100.0),
    )
    _observe(
        tracker,
        "2026-10-06T10:01:10+05:30",
        99.0,
        "BREAKOUT_DOWN",
        _mtf(
            "2026-10-06T10:01:00+05:30",
            open_=100.0,
            high=100.0,
            low=99.0,
            close=99.0,
        ),
    )
    first = _observe(
        tracker,
        "2026-10-06T10:01:20+05:30",
        96.0,
        "BREAKOUT_DOWN",
        _mtf(
            "2026-10-06T10:01:00+05:30",
            open_=99.0,
            high=99.5,
            low=96.0,
            close=96.0,
        ),
    )
    second = _observe(
        tracker,
        "2026-10-06T10:01:40+05:30",
        98.0,
        "BREAKOUT_DOWN",
        _mtf(
            "2026-10-06T10:01:00+05:30",
            open_=96.0,
            high=99.0,
            low=96.0,
            close=98.0,
        ),
    )

    assert first["episode"]["extension_observed"] is False
    assert second["episode"]["extension_observed"] is False
    assert second["ordered_sequence_complete"] is False


def test_oct05_coarse_first_entry_still_does_not_confirm_retest_sequence():
    episode = json.loads(R18C_EPISODE.read_text(encoding="utf-8"))
    tracker = BreakoutRetestShadowTracker("CRUDEOILM")

    result = None
    for index, row in enumerate(episode["cycles"]):
        structure = _structure(low=episode["breakout_level_reference"])
        result = _observe(
            tracker,
            row["timestamp"],
            row["future_ltp"],
            row["regime"],
            {"status": "OK", "timeframes": {}},
            structure=structure,
        )

    assert result is not None
    assert result["ordered_sequence_complete"] is False


def test_shadow_tracker_does_not_mutate_runtime_inputs():
    tracker = BreakoutRetestShadowTracker("CRUDEOILM")
    regime = {"regime": "BREAKOUT_DOWN", "confidence": 0.6}
    structure = _structure(low=100.0)
    mtf = _mtf(
        "2026-10-06T10:01:00+05:30",
        open_=100.0,
        high=100.0,
        low=99.0,
        close=99.0,
    )
    decision = {"action": "BUY_PUT", "SHORT_CONFIDENCE": 80}
    setup = {"setup": "BREAKOUT_RETEST", "blocked": False}

    originals = copy.deepcopy((regime, structure, mtf, decision, setup))

    tracker.observe(
        timestamp="2026-10-06T10:01:00+05:30",
        future_ltp=99.0,
        regime=regime,
        structure=structure,
        mtf=mtf,
        decision=decision,
        setup=setup,
    )

    assert (regime, structure, mtf, decision, setup) == originals


def test_mtf_module_exposes_existing_one_minute_bar_without_new_fetch_surface():
    source = (ROOT / "src" / "mcx" / "mcx_mtf.py").read_text(encoding="utf-8")

    assert '"last_bar_timestamp"' in source
    assert '"last_open"' in source
    assert '"last_high"' in source
    assert '"last_low"' in source
    assert source.count("_fetch_candles(") == 2


def test_runtime_wiring_is_env_gated_and_shadow_only():
    source = (ROOT / "src" / "mcx" / "mcx_paper_bot.py").read_text(encoding="utf-8")

    assert "R18D_CRUDE_RETEST_SHADOW" in source
    assert "BreakoutRetestShadowTracker" in source
    assert "R18D_RETEST_SHADOW_SKIPPED" in source
    assert "mcx_crudeoil_retest_shadow.jsonl" in source

import sys

sys.path.insert(0, "src")

from mcx import mcx_decision as decision


def _inputs():
    chain = {
        "status": "OK",
        "future_ltp": 10000,
        "atm": 10000,
        "pcr_oi": 1.40,
        "max_pain": 10000,
        "ce_data": {},
        "pe_data": {},
        "resistance": [],
        "support": [],
    }

    ctx = {
        "status": "OK",
        "composite_regime": "UP",
        "composite_move_1d_pct": 1.0,
        "primary": {},
        "cross_asset": {},
    }

    mtf = {
        "status": "OK",
        "timeframes": {},
        "aggregate_trend": "BULLISH",
    }

    regime = {
        "regime": "TRENDING_UP",
        "confidence": 0.9,
        "evidence": {},
    }

    return chain, ctx, mtf, regime


def _force_actionable(monkeypatch, captured=None):
    monkeypatch.setattr(
        decision,
        "_technical_direction_score",
        lambda _mtf: (100, {}),
    )

    monkeypatch.setattr(
        decision,
        "_external_context_score",
        lambda _ctx: (100, {}),
    )

    def chain_score(chain, pcr_ema=1.0):
        if captured is not None:
            captured.clear()
            captured.update(chain)

        return 100, {
            "pcr": chain.get("pcr_oi"),
        }

    monkeypatch.setattr(
        decision,
        "_option_chain_score",
        chain_score,
    )

    monkeypatch.setattr(
        decision,
        "_entry_quality_scores",
        lambda *_args, **_kwargs: (100, 0, {}),
    )

    monkeypatch.setattr(
        decision,
        "_combine_scores",
        lambda *_args, **_kwargs: (95, 5),
    )

    monkeypatch.setattr(
        decision,
        "_apply_hard_gates",
        lambda *_args, **_kwargs: [],
    )


def test_explicit_pcr_incomplete_forces_no_trade(monkeypatch):
    captured = {}

    _force_actionable(
        monkeypatch,
        captured=captured,
    )

    chain, ctx, mtf, regime = _inputs()

    result = decision.compose(
        chain,
        ctx,
        mtf,
        regime,
        stable_pcr={
            "status": "PCR_INCOMPLETE",
            "reason": "CHAIN_COVERAGE_6/42",
        },
    )

    assert result["action"] == "NO_TRADE"
    assert result["bias"] == "NEUTRAL"

    assert (
        "STABLE_PCR_PCR_INCOMPLETE"
        in result["HARD_BLOCKERS"]
    )

    # Raw PCR must not silently remain authoritative.
    assert captured.get("pcr_oi") is None
    assert captured.get("pcr_stable_source") is False


def test_explicit_unavailable_stable_pcr_forces_no_trade(monkeypatch):
    _force_actionable(monkeypatch)

    chain, ctx, mtf, regime = _inputs()

    result = decision.compose(
        chain,
        ctx,
        mtf,
        regime,
        stable_pcr={},
    )

    assert result["action"] == "NO_TRADE"
    assert "STABLE_PCR_UNAVAILABLE" in result["HARD_BLOCKERS"]


def test_stable_pcr_ok_remains_action_eligible(monkeypatch):
    captured = {}

    _force_actionable(
        monkeypatch,
        captured=captured,
    )

    chain, ctx, mtf, regime = _inputs()

    result = decision.compose(
        chain,
        ctx,
        mtf,
        regime,
        stable_pcr={
            "status": "OK",
            "PCR_EMA_3": 1.25,
            "PCR_TOTAL_OI": 1.20,
            "PCR_CHANGE_RATE": 2.5,
        },
    )

    assert result["action"] == "BUY_CALL"

    assert not any(
        str(x).startswith("STABLE_PCR_")
        for x in result["HARD_BLOCKERS"]
    )

    assert captured.get("pcr_oi") == 1.25
    assert captured.get("pcr_stable_source") is True


def test_legacy_caller_without_stable_pcr_is_unchanged(monkeypatch):
    captured = {}

    _force_actionable(
        monkeypatch,
        captured=captured,
    )

    chain, ctx, mtf, regime = _inputs()

    result = decision.compose(
        chain,
        ctx,
        mtf,
        regime,
    )

    assert result["action"] == "BUY_CALL"

    assert not any(
        str(x).startswith("STABLE_PCR_")
        for x in result["HARD_BLOCKERS"]
    )

    # Legacy/non-StablePCR caller retains raw chain PCR.
    assert captured.get("pcr_oi") == 1.40

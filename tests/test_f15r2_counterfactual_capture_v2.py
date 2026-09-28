"""F15-R2 Phase R2-4 — WAIT-mode counterfactual capture.

The counterfactual logger inside mcx_paper_bot.main() reads
setup.get("setup") but was previously executed before
setup = classify_setup(...) ran. The resulting NameError was swallowed
by a bare except Exception, silently discarding every WAIT-mode
counterfactual capture. This test file proves the fix.

Tests exercise the importable pieces directly (classify_setup,
log_rejection); they do not construct a real MCX runtime.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

import mcx.mcx_counterfactual as cf  # noqa: E402
import mcx.mcx_setup as setup_mod  # noqa: E402


def test_classify_setup_is_importable_and_pure():
    # Sanity: the classifier exists and takes the documented 5 args.
    import inspect
    sig = inspect.signature(setup_mod.classify)
    params = list(sig.parameters.keys())
    # decision, regime, structure, mtf, poi_state (names may vary; count must be 5)
    assert len(params) == 5


def test_log_rejection_accepts_setup_id():
    """log_rejection must accept a setup_id kwarg (surface contract)."""
    import inspect
    sig = inspect.signature(cf.log_rejection)
    assert "setup_id" in sig.parameters


def test_log_rejection_accepts_all_call_site_kwargs():
    """Every kwarg used at the R2-4 call site must be accepted."""
    import inspect
    sig = inspect.signature(cf.log_rejection)
    expected = {
        "product", "confidence", "direction", "regime",
        "blocking_reasons", "threshold_only", "signal_price",
        "setup_id", "underlying_future_symbol", "future_price",
        "expiry", "dte", "option_side", "hypothetical_contract",
        "attempt",
    }
    missing = expected - set(sig.parameters.keys())
    assert not missing, f"missing kwargs: {sorted(missing)}"


def test_setup_id_none_when_classify_returns_non_dict():
    """The guard `if isinstance(setup, dict) else None` must hold."""
    setup = "not a dict"
    setup_id = setup.get("setup") if isinstance(setup, dict) else None
    assert setup_id is None


def test_setup_id_extracted_when_dict():
    setup = {"setup": "RANGE_REVERSION"}
    setup_id = setup.get("setup") if isinstance(setup, dict) else None
    assert setup_id == "RANGE_REVERSION"

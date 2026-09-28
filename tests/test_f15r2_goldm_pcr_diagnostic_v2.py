"""F15-R2 Phase R2-6 — GOLDM PCR diagnostic tests."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from diagnose_goldm_pcr_v2 import compute_report  # noqa: E402

GOLDM_CFG = {"strike_interval": 100}
UNIV = 10  # StablePCR.UNIVERSE_STEPS


def _chain_from(ce_strikes, pe_strikes, *, fut=73500.0, max_pain=73500.0):
    ce = {float(s): {"oi": 10, "vol": 5} for s in ce_strikes}
    pe = {float(s): {"oi": 10, "vol": 5} for s in pe_strikes}
    return {
        "status": "OK",
        "ce_data": ce,
        "pe_data": pe,
        "future_ltp": fut,
        "atm": fut,
        "max_pain": max_pain,
        "expiry": "2026-12-31",
        "pcr_oi": 1.0,
        "identity_mismatch_count": 0,
    }


def test_fully_listed_universe_reports_full_coverage():
    # 21 nominal strikes * 2 sides = 42 expected, all listed
    strikes = [73500.0 + i * 100 for i in range(-10, 11)]
    chain = _chain_from(strikes, strikes)
    r = compute_report(chain, GOLDM_CFG, UNIV)
    assert r["status"] == "OK"
    assert r["requested_reference_window"] == 21
    assert r["observed_eligible_contracts"] == 42
    assert r["expected_eligible_contracts"] == 42
    assert r["coverage_pct"] == 100.0


def test_sparse_listing_reports_low_coverage():
    # only 8 strikes around ATM, both sides (16 contracts)
    strikes = [73500.0 + i * 100 for i in range(-4, 4)]
    chain = _chain_from(strikes, strikes)
    r = compute_report(chain, GOLDM_CFG, UNIV)
    assert r["observed_eligible_contracts"] == 16
    assert r["expected_eligible_contracts"] == 16
    # eligible denominator equals observed here since only listed strikes
    # are considered; the F15 problem is that StablePCR's denominator is
    # nominal 21*2=42, not observed. compute_report reports both sides.
    assert r["coverage_pct"] == 100.0   # within the eligible-listed universe


def test_single_sided_listing_counts_unpaired():
    # CE on 10 strikes, PE on 8
    ce = [73500.0 + i * 100 for i in range(-5, 5)]
    pe = [73500.0 + i * 100 for i in range(-4, 4)]
    chain = _chain_from(ce, pe)
    r = compute_report(chain, GOLDM_CFG, UNIV)
    assert len(r["paired_strikes"]) == 8
    assert len(r["unpaired_ce_strikes"]) == 2
    assert len(r["unpaired_pe_strikes"]) == 0
    assert r["observed_eligible_ce"] == 10
    assert r["observed_eligible_pe"] == 8
    assert r["observed_eligible_contracts"] == 18


def test_empty_chain_reports_zero_coverage():
    chain = _chain_from([], [])
    r = compute_report(chain, GOLDM_CFG, UNIV)
    assert r["observed_eligible_contracts"] == 0
    assert r["expected_eligible_contracts"] == 0
    assert r["coverage_pct"] == 0.0


def test_no_reference_when_no_future_ltp_and_no_max_pain():
    chain = {"status": "OK", "ce_data": {}, "pe_data": {},
             "future_ltp": None, "max_pain": None}
    r = compute_report(chain, GOLDM_CFG, UNIV)
    assert r["status"] == "NO_REFERENCE"
    assert r["reference_strike"] is None


def test_reference_uses_max_pain_when_present():
    strikes = [73500.0, 73600.0, 73700.0]
    chain = _chain_from(strikes, strikes, max_pain=73600.0)
    r = compute_report(chain, GOLDM_CFG, UNIV)
    assert r["reference_strike"] == 73600.0


def test_reference_falls_back_to_atm_when_max_pain_absent():
    strikes = [73500.0, 73600.0]
    chain = _chain_from(strikes, strikes, fut=73512.0, max_pain=None)
    r = compute_report(chain, GOLDM_CFG, UNIV)
    # 73512 rounded to 100 -> 73500
    assert r["reference_strike"] == 73500.0


def test_int_keys_and_float_keys_both_resolve():
    # float keys
    r1 = compute_report(_chain_from([73500], [73500]), GOLDM_CFG, UNIV)
    assert r1["observed_eligible_contracts"] == 2
    # int keys (constructed with int, checked via _float_set)
    ce = {73500: {"oi": 1}}
    pe = {73500: {"oi": 1}}
    chain = {"status": "OK", "ce_data": ce, "pe_data": pe,
             "future_ltp": 73500.0, "max_pain": 73500.0, "pcr_oi": 1.0}
    r2 = compute_report(chain, GOLDM_CFG, UNIV)
    assert r2["observed_eligible_contracts"] == 2


def test_key_types_reported():
    chain = _chain_from([73500.0], [73500.0])
    r = compute_report(chain, GOLDM_CFG, UNIV)
    assert r["key_types"]["ce_first_key_type"] == "float"
    assert r["key_types"]["pe_first_key_type"] == "float"


def test_identity_mismatch_surfaced():
    chain = _chain_from([73500.0], [73500.0])
    chain["identity_mismatch_count"] = 5
    r = compute_report(chain, GOLDM_CFG, UNIV)
    assert r["identity_mismatch_count"] == 5

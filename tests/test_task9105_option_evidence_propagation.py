from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.certification.task9_option_oi_change_authority import (
    Task9OptionOiChangeAuthority,
    Task9OptionOiSnapshotStore,
)
from services.paper_orchestration.certified_runtime_composition import (
    _propagate_analytical_option_evidence,
)


IST = ZoneInfo("Asia/Kolkata")
T0 = datetime(2026, 8, 26, 9, 30, tzinfo=IST)


def _contract(*, token, strike, side, oi, expiry="01SEP2026", **evidence):
    return {
        "token": token,
        "symbol": f"NIFTY01SEP26{strike}{side}",
        "expiry": expiry,
        "strike": float(strike),
        "option_type": side,
        "open_interest": oi,
        "premium": 100.0,
        "bid": 99.0,
        "ask": 101.0,
        "volume": 1000,
        "lot_size": 65,
        **evidence,
    }


def _raw(contract):
    return {
        **contract,
        "change_in_open_interest": None,
        "iv": None,
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
    }


def test_two_cycle_oi_projection_keeps_new_contract_unavailable(tmp_path):
    authority = Task9OptionOiChangeAuthority(Task9OptionOiSnapshotStore(tmp_path / "oi.json"))
    first = (
        _contract(token="ce", strike=25000, side="CE", oi=1000),
        _contract(token="pe", strike=25000, side="PE", oi=1500),
    )
    authority.enrich(
        underlying_symbol="NIFTY", spot_exchange="NSE", option_exchange="NFO",
        provider_timestamp=T0, contracts=first,
    )
    second = (
        _contract(token="ce", strike=25000, side="CE", oi=1125),
        _contract(token="pe", strike=25000, side="PE", oi=1400),
        _contract(token="new", strike=25100, side="CE", oi=900),
    )
    enriched = authority.enrich(
        underlying_symbol="NIFTY", spot_exchange="NSE", option_exchange="NFO",
        provider_timestamp=T0 + timedelta(minutes=5), contracts=second,
    ).contracts

    projected = _propagate_analytical_option_evidence(
        option_contracts=enriched,
        option_chain_evidence_contracts=tuple(_raw(value) for value in second),
    )

    assert [item["change_in_open_interest"] for item in projected] == [125, -100, None]


def test_nifty_greeks_and_iv_project_only_to_exactly_matched_contract():
    enriched = (
        _contract(
            token="ce", strike=25000, side="CE", oi=1000,
            iv=12.5, delta=0.5, gamma=0.01, theta=-10.0, vega=5.0,
        ),
        _contract(token="pe", strike=25000, side="PE", oi=1000),
    )
    projected = _propagate_analytical_option_evidence(
        option_contracts=enriched,
        option_chain_evidence_contracts=tuple(_raw(value) for value in enriched),
    )

    assert projected[0]["iv"] == 12.5
    assert (projected[0]["delta"], projected[0]["gamma"], projected[0]["theta"], projected[0]["vega"]) == (0.5, 0.01, -10.0, 5.0)
    assert all(projected[1][field] is None for field in ("iv", "delta", "gamma", "theta", "vega"))


def test_conflicting_secondary_identity_fails_closed_without_projection():
    enriched = _contract(token="ce", strike=25000, side="CE", oi=1000, iv=12.5)
    conflicting = _raw(enriched)
    conflicting["expiry"] = "08SEP2026"

    projected = _propagate_analytical_option_evidence(
        option_contracts=(enriched,), option_chain_evidence_contracts=(conflicting,),
    )

    assert projected[0]["iv"] is None


def test_duplicate_token_fails_closed_without_projection():
    first = _contract(token="duplicate", strike=25000, side="CE", oi=1000, iv=12.5)
    second = _contract(token="duplicate", strike=25100, side="CE", oi=1000, iv=14.0)

    projected = _propagate_analytical_option_evidence(
        option_contracts=(first, second),
        option_chain_evidence_contracts=(_raw(first),),
    )

    assert projected[0]["iv"] is None

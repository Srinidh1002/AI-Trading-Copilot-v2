"""B4 X2/X3 contract adapter isolation and honest point-in-time restrictions."""

import sys
from dataclasses import dataclass, replace
from datetime import timedelta
from types import ModuleType

import pytest
from test_x8_readiness_v1 import NOW

from services.x7.contracts_v1 import MARKETS
from services.x8.technical_breadth_bridge_v1 import (
    bind_x2_manifest_to_x8_v1,
    bind_x3_technical_to_x8_v1,
)


@dataclass(frozen=True)
class X3MultiTimeframeResultV1:
    market: str
    instrument_id: str = "instrument"
    as_of: object = NOW
    timeframe_results: tuple = ()

    @property
    def sha256(self):
        from services.x7.contracts_v1 import canonical_sha256

        return canonical_sha256(
            (
                self.market,
                self.instrument_id,
                self.as_of,
                tuple((r.as_of, r.features) for r in self.timeframe_results),
            )
        )


@dataclass(frozen=True)
class X2FeatureManifestV1:
    value: str = "X2"

    def manifest_sha256(self):
        from services.x7.contracts_v1 import canonical_sha256

        return canonical_sha256((self.value, "MANIFEST"))


@pytest.fixture(autouse=True)
def contract_double(monkeypatch):
    # Only the locally isolated test harness substitutes exact upstream classes.
    # The real repo loads actual frozen X2/X3 contracts at these imports.
    x2 = ModuleType("services.x2.feature_manifest_v1")
    x2.X2FeatureManifestV1 = X2FeatureManifestV1
    x3 = ModuleType("services.x3.contracts_v1")
    x3.X3MultiTimeframeResultV1 = X3MultiTimeframeResultV1
    monkeypatch.setitem(sys.modules, x2.__name__, x2)
    monkeypatch.setitem(sys.modules, x3.__name__, x3)


def technical(market="NIFTY", **changes):
    source = X3MultiTimeframeResultV1(market)
    kwargs = dict(
        market=market,
        session_id="session",
        capture_id="capture",
        as_of=NOW + timedelta(seconds=2),
        result=source,
        expected_result_sha256=source.sha256,
        result_available_at=NOW + timedelta(seconds=1),
        max_age_seconds=30,
    )
    kwargs.update(changes)
    return bind_x3_technical_to_x8_v1(**kwargs)


def breadth(market="NIFTY", **changes):
    source = X2FeatureManifestV1()
    kwargs = dict(
        market=market,
        session_id="session",
        capture_id="capture",
        as_of=NOW + timedelta(seconds=2),
        manifest=source if market in ("NIFTY", "SENSEX") else None,
        expected_manifest_sha256=source.manifest_sha256()
        if market in ("NIFTY", "SENSEX")
        else None,
        observed_at=NOW,
        available_at=NOW + timedelta(seconds=1),
    )
    kwargs.update(changes)
    return bind_x2_manifest_to_x8_v1(**kwargs)


@pytest.mark.parametrize("market", MARKETS)
def test_x3_unverified_even_with_matching_hash(market):
    row = technical(market)
    assert row.family == "TECHNICAL" and row.state == "UNAVAILABLE"
    assert not row.point_in_time_verified and not row.independent_vote


@pytest.mark.parametrize("market", MARKETS)
def test_x3_reject_wrong_hash(market):
    with pytest.raises(ValueError, match="hash|SHA"):
        technical(market, expected_result_sha256="f" * 64)


@pytest.mark.parametrize("market", MARKETS)
def test_x3_reject_future_availability(market):
    with pytest.raises(ValueError, match="future"):
        technical(market, result_available_at=NOW + timedelta(seconds=9))


@pytest.mark.parametrize("market", ("NIFTY", "SENSEX"))
def test_x2_manifest_never_upgrades_to_verified_breadth(market):
    row = breadth(market)
    assert row.state == "UNVERIFIED" and not row.point_in_time_verified
    assert row.family == "BREADTH"


@pytest.mark.parametrize("market", MARKETS[2:])
def test_x2_unavailable_for_mcx(market):
    row = breadth(market)
    assert row.state == "UNAVAILABLE" and not row.point_in_time_verified


def test_x2_mcx_cannot_inject_index_manifest():
    with pytest.raises(ValueError, match="MCX"):
        breadth("GOLDM", manifest=X2FeatureManifestV1())


def test_x2_manifest_hash_mismatch_rejected():
    with pytest.raises(ValueError, match="hash"):
        breadth(expected_manifest_sha256="f" * 64)


def test_x3_wrong_market_rejected():
    with pytest.raises(ValueError, match="mismatch"):
        technical(market="SENSEX", result=X3MultiTimeframeResultV1("NIFTY"))


@pytest.mark.parametrize("bad", (0, -1, float("nan"), True, None))
def test_x3_invalid_freshness_budget_rejected(bad):
    with pytest.raises(ValueError):
        technical(max_age_seconds=bad)


def test_x2_no_authority_escalation():
    with pytest.raises(ValueError):
        replace(breadth(), risk_authority=True)


@dataclass(frozen=True)
class Frame:
    as_of: object = NOW
    features: tuple = ()


@pytest.mark.parametrize("market", MARKETS)
def test_present_x3_technical_is_unverified_not_available(market):
    source = X3MultiTimeframeResultV1(market, timeframe_results=(Frame(),))
    row = technical(market, result=source, expected_result_sha256=source.sha256)
    assert row.state == "UNVERIFIED" and row.point_in_time_verified is False


@pytest.mark.parametrize("market", MARKETS)
def test_present_x3_technical_becomes_stale(market):
    source = X3MultiTimeframeResultV1(market, timeframe_results=(Frame(),))
    row = technical(
        market,
        result=source,
        expected_result_sha256=source.sha256,
        as_of=NOW + timedelta(seconds=90),
    )
    assert row.state == "STALE" and not row.point_in_time_verified

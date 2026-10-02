from dataclasses import replace
from datetime import UTC, datetime

import pytest

from services.x3.contracts_v1 import X3FeatureV1, canonical_sha256
from services.x3.family_normalization_v1 import reduce_all_families_v1, reduce_family_v1

NOW = datetime(2026, 9, 18, 9, 30, tzinfo=UTC)


def feature(name, family="MOMENTUM", direction="BULLISH", status="VALID"):
    return X3FeatureV1(
        name,
        "NIFTY",
        "NIFTY-SPOT",
        "5m",
        family,
        1 if status == "VALID" else None,
        "INDEX",
        direction if status == "VALID" else "UNKNOWN",
        status,
        NOW,
        "SERIES-1",
        14,
        50,
        dependency_ids=("OHLC:SERIES-1",),
        blockers=("missing",) if status != "VALID" else (),
    )


def test_contract_hash_repeatable():
    a = feature("RSI")
    assert a.sha256 == canonical_sha256(a) == feature("RSI").sha256
    assert a.to_dict()["observed_at"].startswith("2026-09-18")


def test_invalid_authority_rejected():
    with pytest.raises(ValueError):
        replace(feature("RSI"), execution_authority=True)


def test_invalid_missing_value_rejected():
    with pytest.raises(ValueError):
        replace(feature("RSI"), value=None)


def test_invalid_numeric_rejected():
    with pytest.raises(ValueError):
        replace(feature("RSI"), value=float("nan"))


def test_correlated_many_bulls_have_one_family_state():
    f = reduce_family_v1("MOMENTUM", (feature("MACD"), feature("RSI"), feature("ROC")))
    assert f.state == "BULLISH" and f.member_ids == ("MACD", "ROC", "RSI")
    assert f.shared_dependencies == ("OHLC:SERIES-1",)


def test_opposing_family_signals_are_conflict():
    f = reduce_family_v1("MOMENTUM", (feature("RSI"), feature("MACD", direction="BEARISH")))
    assert f.state == "CONFLICT"


def test_non_directional_exhaustion_does_not_vote():
    f = reduce_family_v1("EXHAUSTION", (feature("CCI", "EXHAUSTION", "NON_DIRECTIONAL"),))
    assert f.state == "NON_DIRECTIONAL"


def test_missing_family_is_explicit():
    f = reduce_family_v1("TREND", ())
    assert f.state == "MISSING"
    assert len(reduce_all_families_v1(())) == 7


def test_non_valid_row_cannot_vote():
    f = reduce_family_v1("MOMENTUM", (feature("RSI", status="UNAVAILABLE"),))
    assert f.state == "MISSING" and f.missing_ids == ("RSI",)


def test_wrong_family_rejected():
    with pytest.raises(ValueError):
        reduce_family_v1("TREND", (feature("RSI"),))

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from services.x2.constituent_universe_v1 import (
    CONSTITUENT_UNIVERSE_SCHEMA_V1,
    ConstituentEntryV1,
    ConstituentUniverseV1,
    WeightUnitV1,
    X2ConstituentError,
    build_constituent_universe_v1,
)

OBSERVED_AT = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
OBS_DATE = date(2026, 9, 30)
EFF_DATE = date(2026, 9, 20)


def entry(
    *,
    cid="HDFCBANK",
    symbol="HDFCBANK-EQ",
    exchange="NSE",
    weight=10.56,
    sector="FINANCIALS",
):
    return {
        "canonical_constituent_id": cid,
        "provider_symbol": symbol,
        "exchange": exchange,
        "weight": weight,
        "sector": sector,
    }


def build(**overrides):
    defaults = dict(
        universe_id="NIFTY_2026_09",
        universe_version="v1",
        index_symbol="NIFTY",
        provider="FYERS",
        weight_unit=WeightUnitV1.PERCENT,
        weight_effective_date=EFF_DATE,
        observation_date=OBS_DATE,
        observed_at=OBSERVED_AT,
        source_id="NSE_INDICES_CSV",
        source_label="NSE published index weights",
        constituents=(
            entry(cid="HDFCBANK", symbol="HDFCBANK-EQ", weight=10.56),
            entry(cid="ICICIBANK", symbol="ICICIBANK-EQ", weight=8.32),
            entry(cid="RELIANCE", symbol="RELIANCE-EQ", weight=8.27),
        ),
        expected_constituent_count=50,
    )
    defaults.update(overrides)
    return build_constituent_universe_v1(**defaults)


def test_build_returns_immutable_universe():
    u = build()
    assert isinstance(u, ConstituentUniverseV1)
    assert u.schema_version == CONSTITUENT_UNIVERSE_SCHEMA_V1
    assert u.observed_constituent_count == 3
    assert u.expected_constituent_count == 50
    assert u.coverage_ratio == pytest.approx(3 / 50)
    assert u.total_weight == pytest.approx(10.56 + 8.32 + 8.27)


def test_entries_are_sorted_deterministically():
    u = build()
    keys = [
        (e.exchange, e.provider_symbol, e.canonical_constituent_id)
        for e in u.constituents
    ]
    assert keys == sorted(keys)


def test_hash_is_deterministic_across_dict_orders():
    a = build(
        constituents={
            "HDFCBANK": entry(cid="HDFCBANK", symbol="HDFCBANK-EQ"),
            "ICICIBANK": entry(cid="ICICIBANK", symbol="ICICIBANK-EQ"),
            "RELIANCE": entry(cid="RELIANCE", symbol="RELIANCE-EQ"),
        }
    )
    b = build(
        constituents={
            "RELIANCE": entry(cid="RELIANCE", symbol="RELIANCE-EQ"),
            "HDFCBANK": entry(cid="HDFCBANK", symbol="HDFCBANK-EQ"),
            "ICICIBANK": entry(cid="ICICIBANK", symbol="ICICIBANK-EQ"),
        }
    )
    assert a.universe_sha256 == b.universe_sha256
    assert a.canonical_json() == b.canonical_json()


def test_rejects_unsupported_index():
    with pytest.raises(X2ConstituentError):
        build(index_symbol="CRUDEOILM")


def test_rejects_unsupported_provider():
    with pytest.raises(X2ConstituentError):
        build(provider="ANGEL_SMARTAPI")


def test_rejects_bad_weight_unit():
    with pytest.raises(X2ConstituentError):
        build(weight_unit="PERCENT")


def test_rejects_non_positive_weight():
    with pytest.raises(X2ConstituentError):
        build(
            constituents=(
                entry(cid="A", symbol="A-EQ", weight=0.0),
            )
        )
    with pytest.raises(X2ConstituentError):
        build(
            constituents=(
                entry(cid="A", symbol="A-EQ", weight=-1.0),
            )
        )
    with pytest.raises(X2ConstituentError):
        build(
            constituents=(
                entry(cid="A", symbol="A-EQ", weight=float("nan")),
            )
        )


def test_rejects_duplicate_canonical_id():
    with pytest.raises(X2ConstituentError):
        build(
            constituents=(
                entry(cid="A", symbol="A-EQ", weight=1.0),
                entry(cid="A", symbol="A2-EQ", weight=1.0),
            )
        )


def test_rejects_duplicate_provider_symbol():
    with pytest.raises(X2ConstituentError):
        build(
            constituents=(
                entry(cid="A", symbol="SAME-EQ", weight=1.0),
                entry(cid="B", symbol="SAME-EQ", weight=1.0),
            )
        )


def test_rejects_weight_effective_date_after_observation():
    with pytest.raises(X2ConstituentError):
        build(
            weight_effective_date=date(2026, 10, 1),
            observation_date=date(2026, 9, 30),
        )


def test_rejects_partial_without_reason():
    with pytest.raises(X2ConstituentError):
        build(is_partial=True, missing_reason=None)


def test_rejects_complete_with_reason():
    with pytest.raises(X2ConstituentError):
        build(is_partial=False, missing_reason="leftover")


def test_partial_universe_does_not_renormalise_weights():
    u = build(
        is_partial=True,
        missing_reason="only top weights retrieved",
    )
    assert u.total_weight < 100.0
    assert u.is_partial is True


def test_expected_count_must_not_be_below_observed():
    with pytest.raises(X2ConstituentError):
        build(expected_constituent_count=2)


def test_entry_rejects_empty_exchange_and_uppercases_it():
    with pytest.raises(X2ConstituentError):
        ConstituentEntryV1(
            canonical_constituent_id="A",
            provider_symbol="A-EQ",
            exchange="",
            weight=1.0,
        )
    e = ConstituentEntryV1(
        canonical_constituent_id="A",
        provider_symbol="A-EQ",
        exchange="nse",
        weight=1.0,
    )
    assert e.exchange == "NSE"


def test_canonical_payload_is_json_safe():
    import json

    u = build()
    payload = u.canonical_payload()
    json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert payload["schema_version"] == CONSTITUENT_UNIVERSE_SCHEMA_V1


def test_sensex_index_exchange_is_enforced():
    u = build_constituent_universe_v1(
        universe_id="SENSEX_2026_09",
        universe_version="v1",
        index_symbol="SENSEX",
        provider="FYERS",
        weight_unit=WeightUnitV1.PERCENT,
        weight_effective_date=EFF_DATE,
        observation_date=OBS_DATE,
        observed_at=OBSERVED_AT,
        source_id="BSE_WEIGHTS",
        source_label="BSE published weights",
        constituents=(
            entry(
                cid="RELIANCE",
                symbol="RELIANCE-EQ",
                exchange="BSE",
                weight=10.64,
            ),
        ),
        expected_constituent_count=30,
    )
    assert u.index_exchange == "BSE"


def test_data_only_flags():
    u = build()
    assert u.schema_version == CONSTITUENT_UNIVERSE_SCHEMA_V1
    for attr in (
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
    ):
        assert not hasattr(u, attr) or getattr(u, attr) is False

"""Offline X4 contract, contamination, quality, numeric and safety tests."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from services.x4.contracts_v1 import X4BasisReferenceV1, X4ContractV1, X4SampleV1
from services.x4.futures_engine_v1 import analyze_futures_v1

NOW = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
MARKETS = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")


def contract(market="NIFTY"):
    return X4ContractV1(
        market=market,
        canonical_instrument_id=f"FYERS:{market}:FUT:OCT",
        provider="FYERS",
        provider_symbol=f"FUT:{market}",
        expiry=date(2026, 10, 30),
        price_unit="INDEX_POINTS" if market in {"NIFTY", "SENSEX"} else "INR_PER_QUOTE_UNIT",
        metadata_status="VERIFIED",
        metadata_source="TEST_VERIFIED_MASTER",
    )


def samples(
    c, prices=(100.0, 101.0, 102.0), oi=(1000.0, 1010.0, 1030.0), volume=(10.0, 20.0, 30.0)
):
    return tuple(
        X4SampleV1(
            contract_id=c.canonical_instrument_id,
            session_id="2026-10-01:S1",
            timeframe="5m",
            observed_at=NOW - timedelta(minutes=10 - i * 5),
            source_id="TEST_CAPTURE",
            close=price,
            high=price + 1,
            low=price - 1,
            volume=volume[i],
            open_interest=oi[i],
            volume_verified=True,
            oi_verified=True,
            is_closed=True,
            quality="VALID",
        )
        for i, price in enumerate(prices)
    )


def analyze(c, rows, **kwargs):
    return analyze_futures_v1(contract=c, samples=rows, as_of=NOW, max_age_seconds=90, **kwargs)


def feature(result, key):
    return next(f for f in result.features if f.feature_id == key)


@pytest.mark.parametrize("market", MARKETS)
def test_five_markets_same_contract_safe(market):
    c = contract(market)
    s = samples(c)
    r = analyze(c, s)
    assert r.market == market and r.instrument_id == c.canonical_instrument_id
    assert r.positioning_state == "LONG_BUILDUP"
    assert r.sha256() == analyze(c, s).sha256()
    assert r.data_only and r.live_execution_eligible is False
    assert all(
        f.data_only and not f.execution_authority and not f.certification_authority
        for f in r.features
    )


@pytest.mark.parametrize(
    "price,oi,expected",
    [
        (102.0, 1030.0, "LONG_BUILDUP"),
        (98.0, 1030.0, "SHORT_BUILDUP"),
        (102.0, 970.0, "SHORT_COVERING"),
        (98.0, 970.0, "LONG_UNWINDING"),
        (100.0, 1000.0, "FLAT"),
    ],
)
def test_price_oi_states(price, oi, expected):
    c = contract()
    s = samples(c, prices=(99.0, 100.0, price), oi=(990.0, 1000.0, oi))
    assert analyze(c, s).positioning_state == expected


def test_oi_acceleration_time_normalized():
    c = contract()
    f = feature(analyze(c, samples(c)), "FUTURES_OI_ACCELERATION")
    # OI increases by 10 then 20 over consecutive five-minute bars.
    assert f.status == "AVAILABLE"
    assert f.value == pytest.approx(1440.0)


def test_vwap_is_labeled_estimate_not_true_vwap():
    c = contract()
    r = analyze(c, samples(c))
    f = feature(r, "FUTURES_CANDLE_VWAP_ESTIMATE")
    assert f.status == "AVAILABLE"
    assert f.value == pytest.approx((100 * 10 + 101 * 20 + 102 * 30) / 60)
    assert "ESTIMATE" in f.feature_id


def test_missing_volume_fails_closed_for_estimate():
    c = contract()
    s = samples(c)
    s = (replace(s[0], volume_verified=False), *s[1:])
    r = analyze(c, tuple(s))
    assert feature(r, "FUTURES_CANDLE_VWAP_ESTIMATE").status == "UNAVAILABLE"


def test_missing_oi_does_not_invent_positioning_or_acceleration():
    c = contract()
    s = samples(c)
    s = (*s[:-1], replace(s[-1], oi_verified=False))
    r = analyze(c, tuple(s))
    assert r.positioning_state == "UNKNOWN"
    assert feature(r, "FUTURES_OI_CHANGE_PCT").value is None
    assert feature(r, "FUTURES_OI_ACCELERATION").status == "UNAVAILABLE"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c, s: (*s[:-1], replace(s[-1], contract_id="OTHER")),
        lambda c, s: (*s[:-1], replace(s[-1], session_id="OTHER_SESSION")),
        lambda c, s: (*s[:-1], replace(s[-1], timeframe="1m")),
        lambda c, s: (*s[:-1], replace(s[-1], quality="STALE")),
        lambda c, s: (*s[:-1], replace(s[-1], is_closed=False)),
        lambda c, s: (*s[:-1], replace(s[-1], observed_at=NOW + timedelta(seconds=1))),
        lambda c, s: (*s[:-1], replace(s[-1], observed_at=s[-2].observed_at)),
    ],
)
def test_reject_contaminated_input(mutation):
    c = contract()
    with pytest.raises(ValueError):
        analyze(c, tuple(mutation(c, samples(c))))


def test_stale_asof_fails_closed():
    c = contract()
    result = analyze_futures_v1(
        contract=c, samples=samples(c), as_of=NOW + timedelta(hours=1), max_age_seconds=90
    )
    assert result.status == "UNAVAILABLE" and not result.features


def test_unverified_contract_fails_closed():
    c = replace(contract(), metadata_status="PROVISIONAL")
    result = analyze(c, samples(c))
    assert result.status == "UNAVAILABLE" and result.positioning_state == "UNKNOWN"


def test_no_basis_without_verified_reference():
    c = contract("NIFTY")
    assert feature(analyze(c, samples(c)), "FUTURES_BASIS").value is None


def test_verified_index_basis():
    c = contract("NIFTY")
    ref = X4BasisReferenceV1(
        market="NIFTY",
        benchmark_type="INDEX_SPOT",
        price=101,
        price_unit="INDEX_POINTS",
        source_id="VERIFIED_SPOT",
        observed_at=NOW,
        verified=True,
    )
    assert feature(analyze(c, samples(c), basis_reference=ref), "FUTURES_BASIS").value == 1


def test_mcx_index_reference_does_not_fake_spot_basis():
    c = contract("GOLDM")
    ref = X4BasisReferenceV1(
        market="GOLDM",
        benchmark_type="INDEX_SPOT",
        price=101,
        price_unit="INR_PER_QUOTE_UNIT",
        source_id="BAD_BENCHMARK",
        observed_at=NOW,
        verified=True,
    )
    f = feature(analyze(c, samples(c), basis_reference=ref), "FUTURES_BASIS")
    assert f.status == "NOT_APPLICABLE" and f.value is None


def test_nan_and_zero_oi_rejected():
    c = contract()
    with pytest.raises(ValueError):
        replace(samples(c)[-1], open_interest=0)
    with pytest.raises(ValueError):
        replace(samples(c)[-1], close=float("nan"))


def test_requires_explicit_closed_valid_data():
    c = contract()
    with pytest.raises(ValueError):
        analyze(
            c,
            (
                X4SampleV1(
                    contract_id=c.canonical_instrument_id,
                    session_id="S1",
                    timeframe="5m",
                    observed_at=NOW,
                    source_id="TEST",
                    close=100,
                ),
            ),
        )


def test_same_day_mcx_expiry_fails_closed():
    c = replace(contract("CRUDEOILM"), expiry=date(2026, 10, 1))
    assert analyze(c, samples(c)).status == "UNAVAILABLE"


def test_same_day_index_expiry_after_market_close_fails_closed():
    c = replace(contract("NIFTY"), expiry=date(2026, 10, 1))
    result = analyze_futures_v1(
        contract=c,
        samples=samples(c),
        as_of=datetime(2026, 10, 1, 16, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        max_age_seconds=30000,
    )
    assert result.status == "UNAVAILABLE"


def test_source_provenance_in_feature_dependency_ids():
    c = contract()
    r = analyze(c, samples(c))
    assert "TEST_CAPTURE" in r.features[0].dependency_ids

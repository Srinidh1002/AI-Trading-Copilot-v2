from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from services.x2.constituent_universe_v1 import (
    WeightUnitV1,
    X2ConstituentError,
    build_constituent_universe_v1,
)
from services.x2.sector_strength_v1 import (
    SECTOR_STRENGTH_SCHEMA_V1,
    PreviousSectorSnapshotV1,
    RotationStatusV1,
    SectorReturnInputV1,
    compute_sector_strength_v1,
)

OBSERVED_AT = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
OBS_DATE = date(2026, 9, 30)
EFF_DATE = date(2026, 9, 20)


def entry(cid, weight, sector, exchange="NSE"):
    return {
        "canonical_constituent_id": cid,
        "provider_symbol": f"{cid}-EQ",
        "exchange": exchange,
        "weight": weight,
        "sector": sector,
    }


def universe(*, entries=None, expected=6):
    if entries is None:
        entries = (
            entry("A", 10.0, "FIN"),
            entry("B", 8.0, "FIN"),
            entry("C", 6.0, "IT"),
            entry("D", 5.0, "IT"),
            entry("E", 4.0, "ENERGY"),
            entry("F", 3.0, "ENERGY"),
        )
    entries = tuple(entries)
    if expected < len(entries):
        entries = entries[:expected]
    return build_constituent_universe_v1(
        universe_id="NIFTY_2026_09",
        universe_version="v1",
        index_symbol="NIFTY",
        provider="FYERS",
        weight_unit=WeightUnitV1.PERCENT,
        weight_effective_date=EFF_DATE,
        observation_date=OBS_DATE,
        observed_at=OBSERVED_AT,
        source_id="NSE_INDICES_CSV",
        source_label="NSE published weights",
        constituents=entries,
        expected_constituent_count=expected,
    )


def inp(cid, ret, *, at=None):
    return SectorReturnInputV1(
        canonical_constituent_id=cid,
        return_fraction=ret,
        observed_at=at or OBSERVED_AT,
    )


def test_sector_weighted_return_basic():
    u = universe()
    inputs = {
        "A": inp("A", 0.02),
        "B": inp("B", 0.01),
        "C": inp("C", -0.01),
        "D": inp("D", -0.005),
        "E": inp("E", 0.0),
        "F": inp("F", 0.0),
    }
    r = compute_sector_strength_v1(
        universe=u,
        inputs=inputs,
        calculated_at=OBSERVED_AT,
        horizon="1d",
    )
    by_sector = {row.sector: row for row in r.rows}
    # FIN: (10*0.02 + 8*0.01) / 18 = 0.28 / 18
    assert by_sector["FIN"].sector_weighted_return == pytest.approx(
        (10 * 0.02 + 8 * 0.01) / 18
    )
    # IT: (6*-0.01 + 5*-0.005) / 11
    assert by_sector["IT"].sector_weighted_return == pytest.approx(
        (6 * -0.01 + 5 * -0.005) / 11
    )


def test_index_weighted_return_used_for_relative():
    u = universe()
    inputs = {
        "A": inp("A", 0.02),
        "B": inp("B", 0.01),
        "C": inp("C", -0.01),
        "D": inp("D", -0.005),
        "E": inp("E", 0.0),
        "F": inp("F", 0.0),
    }
    r = compute_sector_strength_v1(
        universe=u, inputs=inputs, calculated_at=OBSERVED_AT, horizon="1d"
    )
    # Index weighted return uses total observed weight across all sectors.
    weights = [10, 8, 6, 5, 4, 3]
    rets = [0.02, 0.01, -0.01, -0.005, 0.0, 0.0]
    expected_index = sum(w * r_ for w, r_ in zip(weights, rets)) / sum(weights)
    assert r.index_weighted_return == pytest.approx(expected_index)
    by_sector = {row.sector: row for row in r.rows}
    assert by_sector["FIN"].sector_relative_return == pytest.approx(
        by_sector["FIN"].sector_weighted_return - expected_index
    )


def test_advancing_declining_unchanged_counts():
    u = universe(expected=4)
    inputs = {
        "A": inp("A", 0.02),
        "B": inp("B", -0.02),
        "C": inp("C", 0.0),
        "D": inp("D", 0.005),
    }
    r = compute_sector_strength_v1(
        universe=u,
        inputs=inputs,
        calculated_at=OBSERVED_AT,
        horizon="1d",
        unchanged_band_pct=0.0005,  # 0.05% as a fraction
    )
    by_sector = {row.sector: row for row in r.rows}
    assert by_sector["FIN"].advancing_count == 1
    assert by_sector["FIN"].declining_count == 1
    assert by_sector["IT"].advancing_count == 1
    assert by_sector["IT"].unchanged_count == 1


def test_top_contributor_and_detractor():
    u = universe(expected=3)
    inputs = {
        "A": inp("A", 0.05),
        "B": inp("B", -0.05),
        "C": inp("C", 0.01),
    }
    r = compute_sector_strength_v1(
        universe=u, inputs=inputs, calculated_at=OBSERVED_AT, horizon="1d"
    )
    by_sector = {row.sector: row for row in r.rows}
    assert by_sector["FIN"].top_contributor == "A"
    assert by_sector["FIN"].top_detractor == "B"


def test_missing_input_is_recorded_not_skipped():
    u = universe(expected=4)
    inputs = {
        "A": inp("A", 0.02),
        # B omitted
        "C": inp("C", 0.01),
        "D": inp("D", 0.0),
    }
    r = compute_sector_strength_v1(
        universe=u, inputs=inputs, calculated_at=OBSERVED_AT, horizon="1d"
    )
    assert "B" in r.missing_constituents
    assert r.is_partial is True
    assert r.evidence_status == "PARTIAL"


def test_stale_input_is_recorded_not_admitted():
    u = universe(expected=4)
    stale_at = OBSERVED_AT - timedelta(seconds=600)
    inputs = {
        "A": inp("A", 0.02),
        "B": inp("B", 0.02, at=stale_at),
        "C": inp("C", 0.01),
        "D": inp("D", 0.0),
    }
    r = compute_sector_strength_v1(
        universe=u,
        inputs=inputs,
        calculated_at=OBSERVED_AT,
        horizon="1d",
        stale_after_seconds=60.0,
    )
    assert "B" in r.stale_constituents


def test_unsectored_constituent_is_recorded():
    u = build_constituent_universe_v1(
        universe_id="NIFTY_2026_09",
        universe_version="v1",
        index_symbol="NIFTY",
        provider="FYERS",
        weight_unit=WeightUnitV1.PERCENT,
        weight_effective_date=EFF_DATE,
        observation_date=OBS_DATE,
        observed_at=OBSERVED_AT,
        source_id="NSE_INDICES_CSV",
        source_label="NSE published weights",
        constituents=(
            entry("A", 10.0, "FIN"),
            {
                "canonical_constituent_id": "B",
                "provider_symbol": "B-EQ",
                "exchange": "NSE",
                "weight": 8.0,
                "sector": None,
            },
        ),
        expected_constituent_count=2,
    )
    inputs = {"A": inp("A", 0.02), "B": inp("B", 0.01)}
    r = compute_sector_strength_v1(
        universe=u, inputs=inputs, calculated_at=OBSERVED_AT, horizon="1d"
    )
    assert "B" in r.unsectored_constituents
    assert r.is_partial is True


def test_rotation_requires_previous_snapshot():
    u = universe()
    inputs = {
        "A": inp("A", 0.02),
        "B": inp("B", 0.01),
        "C": inp("C", -0.01),
        "D": inp("D", -0.005),
        "E": inp("E", 0.0),
        "F": inp("F", 0.0),
    }
    r = compute_sector_strength_v1(
        universe=u, inputs=inputs, calculated_at=OBSERVED_AT, horizon="1d"
    )
    assert (
        r.rotation_overall_status
        == RotationStatusV1.INSUFFICIENT_HISTORY
    )
    assert all(
        rot.rotation_status == RotationStatusV1.INSUFFICIENT_HISTORY
        for rot in r.rotations
    )


def test_rotation_detected_on_rank_and_relative_return_change():
    u = universe()
    inputs = {
        "A": inp("A", 0.03),   # FIN strong
        "B": inp("B", 0.02),
        "C": inp("C", -0.02),  # IT weak
        "D": inp("D", -0.01),
        "E": inp("E", 0.0),
        "F": inp("F", 0.0),
    }
    prev = PreviousSectorSnapshotV1(
        captured_at=OBSERVED_AT - timedelta(hours=1),
        horizon="1d",
        sector_ranks=(
            ("IT", 1),
            ("FIN", 3),
            ("ENERGY", 2),
        ),
        sector_relative_returns=(
            ("IT", 0.02),
            ("FIN", -0.02),
            ("ENERGY", 0.0),
        ),
    )
    r = compute_sector_strength_v1(
        universe=u,
        inputs=inputs,
        calculated_at=OBSERVED_AT,
        horizon="1d",
        previous_snapshot=prev,
        rotation_rank_threshold=1,
        rotation_relative_return_threshold=0.001,
    )
    assert r.rotation_overall_status == RotationStatusV1.ROTATION
    by_sector = {rot.sector: rot for rot in r.rotations}
    assert (
        by_sector["FIN"].rotation_status
        == RotationStatusV1.ROTATION
    )


def test_rotation_not_declared_on_small_change():
    u = universe()
    inputs = {
        "A": inp("A", 0.02),
        "B": inp("B", 0.01),
        "C": inp("C", -0.01),
        "D": inp("D", -0.005),
        "E": inp("E", 0.0),
        "F": inp("F", 0.0),
    }
    prev = PreviousSectorSnapshotV1(
        captured_at=OBSERVED_AT - timedelta(hours=1),
        horizon="1d",
        sector_ranks=(("FIN", 1), ("IT", 2), ("ENERGY", 3)),
        sector_relative_returns=(
            ("FIN", 0.01),
            ("IT", -0.01),
            ("ENERGY", 0.0),
        ),
    )
    r = compute_sector_strength_v1(
        universe=u,
        inputs=inputs,
        calculated_at=OBSERVED_AT,
        horizon="1d",
        previous_snapshot=prev,
        rotation_rank_threshold=2,
        rotation_relative_return_threshold=0.02,
    )
    assert r.rotation_overall_status != RotationStatusV1.ROTATION


def test_rotation_single_sector_insufficient():
    # Only one sector => cannot rank, so rotation is INSUFFICIENT_HISTORY
    u = universe(
        entries=(entry("A", 10.0, "FIN"), entry("B", 8.0, "FIN")),
        expected=2,
    )
    inputs = {"A": inp("A", 0.02), "B": inp("B", 0.01)}
    prev = PreviousSectorSnapshotV1(
        captured_at=OBSERVED_AT - timedelta(hours=1),
        horizon="1d",
        sector_ranks=(("FIN", 1),),
        sector_relative_returns=(("FIN", 0.0),),
    )
    r = compute_sector_strength_v1(
        universe=u,
        inputs=inputs,
        calculated_at=OBSERVED_AT,
        horizon="1d",
        previous_snapshot=prev,
    )
    assert (
        r.rotation_overall_status
        == RotationStatusV1.INSUFFICIENT_HISTORY
    )


def test_hash_is_deterministic_across_input_order():
    u = universe()
    a = {
        "A": inp("A", 0.02),
        "B": inp("B", 0.01),
        "C": inp("C", -0.01),
        "D": inp("D", -0.005),
        "E": inp("E", 0.0),
        "F": inp("F", 0.0),
    }
    b = {
        "F": inp("F", 0.0),
        "E": inp("E", 0.0),
        "D": inp("D", -0.005),
        "C": inp("C", -0.01),
        "B": inp("B", 0.01),
        "A": inp("A", 0.02),
    }
    ra = compute_sector_strength_v1(
        universe=u, inputs=a, calculated_at=OBSERVED_AT, horizon="1d"
    )
    rb = compute_sector_strength_v1(
        universe=u, inputs=b, calculated_at=OBSERVED_AT, horizon="1d"
    )
    assert ra.result_sha256 == rb.result_sha256


def test_rejects_bad_inputs():
    u = universe()
    with pytest.raises(X2ConstituentError):
        compute_sector_strength_v1(
            universe=None,  # type: ignore[arg-type]
            inputs={},
            calculated_at=OBSERVED_AT,
            horizon="1d",
        )
    with pytest.raises(X2ConstituentError):
        compute_sector_strength_v1(
            universe=u,
            inputs=None,  # type: ignore[arg-type]
            calculated_at=OBSERVED_AT,
            horizon="1d",
        )
    with pytest.raises(X2ConstituentError):
        compute_sector_strength_v1(
            universe=u,
            inputs={},
            calculated_at=OBSERVED_AT,
            horizon="",
        )
    with pytest.raises(X2ConstituentError):
        compute_sector_strength_v1(
            universe=u,
            inputs={},
            calculated_at=datetime(2026, 9, 30, 10, 0),  # naive
            horizon="1d",
        )
    with pytest.raises(X2ConstituentError):
        compute_sector_strength_v1(
            universe=u,
            inputs={},
            calculated_at=OBSERVED_AT,
            horizon="1d",
            previous_snapshot="not a snapshot",  # type: ignore[arg-type]
        )


def test_empty_inputs_gives_unavailable():
    u = universe()
    r = compute_sector_strength_v1(
        universe=u, inputs={}, calculated_at=OBSERVED_AT, horizon="1d"
    )
    assert r.evidence_status == "UNAVAILABLE"
    assert r.rows == ()


def test_schema_version():
    u = universe()
    r = compute_sector_strength_v1(
        universe=u,
        inputs={"A": inp("A", 0.01)},
        calculated_at=OBSERVED_AT,
        horizon="1d",
    )
    assert r.schema_version == SECTOR_STRENGTH_SCHEMA_V1

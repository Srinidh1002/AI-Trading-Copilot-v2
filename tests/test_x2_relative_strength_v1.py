from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from services.x2.constituent_universe_v1 import X2ConstituentError
from services.x2.relative_strength_v1 import (
    RELATIVE_STRENGTH_SCHEMA_V1,
    RelativeStrengthClassV1,
    RelativeStrengthStatusV1,
    ReturnObservationV1,
    compute_relative_strength_v1,
)

NOW = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)


def obs(identity, ret, *, at=None, horizon="1d"):
    return ReturnObservationV1(
        identity=identity,
        return_fraction=ret,
        observed_at=at or NOW,
        horizon=horizon,
    )


def pairs(*items):
    return tuple(items)


def test_outperforming_classification():
    observations = {
        "RELIANCE": obs("RELIANCE", 0.02),
        "NIFTY": obs("NIFTY", 0.005),
    }
    r = compute_relative_strength_v1(
        observations=observations,
        calculated_at=NOW,
        horizon="1d",
        pairs_to_compute=pairs(("RELIANCE", "NIFTY", "CONSTITUENT_VS_INDEX")),
    )
    assert r.evidence_status == "READY"
    pair = r.pairs[0]
    assert pair.status == RelativeStrengthStatusV1.OK
    assert pair.relative_return == pytest.approx(0.015)
    assert pair.classification == RelativeStrengthClassV1.OUTPERFORMING


def test_underperforming_classification():
    observations = {
        "RELIANCE": obs("RELIANCE", -0.01),
        "NIFTY": obs("NIFTY", 0.005),
    }
    r = compute_relative_strength_v1(
        observations=observations,
        calculated_at=NOW,
        horizon="1d",
        pairs_to_compute=pairs(("RELIANCE", "NIFTY", "CONSTITUENT_VS_INDEX")),
    )
    assert (
        r.pairs[0].classification
        == RelativeStrengthClassV1.UNDERPERFORMING
    )


def test_neutral_within_band():
    observations = {
        "A": obs("A", 0.010),
        "B": obs("B", 0.0098),
    }
    r = compute_relative_strength_v1(
        observations=observations,
        calculated_at=NOW,
        horizon="1d",
        pairs_to_compute=pairs(("A", "B", "CONSTITUENT_VS_INDEX")),
        neutral_band=0.0005,
    )
    assert (
        r.pairs[0].classification == RelativeStrengthClassV1.NEUTRAL
    )


def test_unaligned_timestamps_are_not_admitted():
    observations = {
        "A": obs("A", 0.02, at=NOW),
        "B": obs("B", 0.01, at=NOW + timedelta(seconds=1)),
    }
    r = compute_relative_strength_v1(
        observations=observations,
        calculated_at=NOW + timedelta(seconds=10),
        horizon="1d",
        pairs_to_compute=pairs(("A", "B", "CONSTITUENT_VS_INDEX")),
    )
    pair = r.pairs[0]
    assert pair.status == RelativeStrengthStatusV1.UNALIGNED
    assert pair.relative_return is None
    assert r.evidence_status == "UNAVAILABLE"


def test_mismatched_horizons_are_not_admitted():
    observations = {
        "A": obs("A", 0.02, horizon="1d"),
        "B": obs("B", 0.01, horizon="1h"),
    }
    r = compute_relative_strength_v1(
        observations=observations,
        calculated_at=NOW,
        horizon="1d",
        pairs_to_compute=pairs(("A", "B", "CONSTITUENT_VS_INDEX")),
    )
    assert r.pairs[0].status == RelativeStrengthStatusV1.UNALIGNED


def test_insufficient_history_recorded_per_pair():
    observations = {
        "A": obs("A", 0.02),
        "B": obs("B", 0.01),
    }
    r = compute_relative_strength_v1(
        observations=observations,
        calculated_at=NOW,
        horizon="1d",
        pairs_to_compute=pairs(
            ("A", "B", "CONSTITUENT_VS_INDEX"),
            ("MISSING", "B", "CONSTITUENT_VS_INDEX"),
        ),
    )
    assert r.evidence_status == "PARTIAL"
    by_subject = {p.subject: p for p in r.pairs}
    assert (
        by_subject["MISSING"].status
        == RelativeStrengthStatusV1.INSUFFICIENT_HISTORY
    )
    assert (
        by_subject["A"].status == RelativeStrengthStatusV1.OK
    )


def test_nifty_vs_sensex_isolated():
    observations = {
        "NIFTY": obs("NIFTY", 0.005),
        "SENSEX": obs("SENSEX", 0.007),
    }
    r = compute_relative_strength_v1(
        observations=observations,
        calculated_at=NOW,
        horizon="1d",
        pairs_to_compute=pairs(("NIFTY", "SENSEX", "INDEX_VS_INDEX")),
    )
    assert r.nifty_vs_sensex is not None
    assert r.nifty_vs_sensex.subject == "NIFTY"
    assert r.nifty_vs_sensex.benchmark == "SENSEX"
    assert r.nifty_vs_sensex.relative_return == pytest.approx(-0.002)


def test_relative_outperformance_does_not_imply_absolute_bullish():
    # A constituent up 0.5% vs benchmark up 2.0% is a relative
    # underperformer. The engine must not label it bullish.
    observations = {
        "A": obs("A", 0.005),
        "B": obs("B", 0.02),
    }
    r = compute_relative_strength_v1(
        observations=observations,
        calculated_at=NOW,
        horizon="1d",
        pairs_to_compute=pairs(("A", "B", "CONSTITUENT_VS_INDEX")),
    )
    payload = r.canonical_json().lower()
    for forbidden in ("bullish", "bearish", "buy", "sell"):
        assert forbidden not in payload
    assert (
        r.pairs[0].classification
        == RelativeStrengthClassV1.UNDERPERFORMING
    )


def test_hash_is_deterministic_across_pair_order():
    observations = {
        "A": obs("A", 0.02),
        "B": obs("B", 0.01),
        "C": obs("C", -0.005),
    }
    a = compute_relative_strength_v1(
        observations=observations,
        calculated_at=NOW,
        horizon="1d",
        pairs_to_compute=pairs(
            ("A", "B", "CONSTITUENT_VS_INDEX"),
            ("C", "B", "CONSTITUENT_VS_INDEX"),
        ),
    )
    b = compute_relative_strength_v1(
        observations=observations,
        calculated_at=NOW,
        horizon="1d",
        pairs_to_compute=pairs(
            ("C", "B", "CONSTITUENT_VS_INDEX"),
            ("A", "B", "CONSTITUENT_VS_INDEX"),
        ),
    )
    assert a.result_sha256 == b.result_sha256


def test_rejects_bad_inputs():
    with pytest.raises(X2ConstituentError):
        compute_relative_strength_v1(
            observations=None,  # type: ignore[arg-type]
            calculated_at=NOW,
            horizon="1d",
            pairs_to_compute=pairs(("A", "B", "X")),
        )
    with pytest.raises(X2ConstituentError):
        compute_relative_strength_v1(
            observations={},
            calculated_at=NOW,
            horizon="",
            pairs_to_compute=pairs(("A", "B", "X")),
        )
    with pytest.raises(X2ConstituentError):
        compute_relative_strength_v1(
            observations={},
            calculated_at=NOW,
            horizon="1d",
            pairs_to_compute=(),  # empty not allowed
        )
    with pytest.raises(X2ConstituentError):
        compute_relative_strength_v1(
            observations={},
            calculated_at=NOW,
            horizon="1d",
            pairs_to_compute=pairs(("A",)),  # malformed
        )
    with pytest.raises(X2ConstituentError):
        compute_relative_strength_v1(
            observations={},
            calculated_at=NOW,
            horizon="1d",
            pairs_to_compute=pairs(("A", "B", "X")),
            neutral_band=-1,
        )
    with pytest.raises(X2ConstituentError):
        compute_relative_strength_v1(
            observations={},
            calculated_at=datetime(2026, 9, 30, 10, 0),  # naive
            horizon="1d",
            pairs_to_compute=pairs(("A", "B", "X")),
        )


def test_observation_validation():
    with pytest.raises(X2ConstituentError):
        ReturnObservationV1(
            identity="",
            return_fraction=0.01,
            observed_at=NOW,
            horizon="1d",
        )
    with pytest.raises(X2ConstituentError):
        ReturnObservationV1(
            identity="A",
            return_fraction=float("nan"),
            observed_at=NOW,
            horizon="1d",
        )
    with pytest.raises(X2ConstituentError):
        ReturnObservationV1(
            identity="A",
            return_fraction=0.01,
            observed_at=datetime(2026, 9, 30, 10, 0),  # naive
            horizon="1d",
        )
    with pytest.raises(X2ConstituentError):
        ReturnObservationV1(
            identity="A",
            return_fraction=0.01,
            observed_at=NOW,
            horizon="",
        )


def test_schema_version():
    observations = {"A": obs("A", 0.02), "B": obs("B", 0.01)}
    r = compute_relative_strength_v1(
        observations=observations,
        calculated_at=NOW,
        horizon="1d",
        pairs_to_compute=pairs(("A", "B", "CONSTITUENT_VS_INDEX")),
    )
    assert r.schema_version == RELATIVE_STRENGTH_SCHEMA_V1

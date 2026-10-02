"""X7-B1 global and India VIX adapter: source fidelity, time, units, isolation."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from services.x7.contracts_v1 import (
    GLOBAL_TYPES,
    GLOBAL_UNITS,
    MARKETS,
    X7ContextCaptureV1,
)
from services.x7.global_adapter_v1 import (
    X7GlobalAdaptedObservationV1,
    X7GlobalBatchV1,
    X7GlobalSourceProofV1,
    adapt_x7_global_batch_v1,
    adapt_x7_global_observation_v1,
)
from services.x7.input_validation_v1 import validate_x7_context_v1

T0 = datetime(2026, 10, 1, 7, 0, tzinfo=UTC)
T1 = T0 + timedelta(seconds=30)
T2 = T1 + timedelta(seconds=30)
NOW = T2 + timedelta(seconds=90)


def proof(name="SP500", **updates):
    p = dict(
        name=name,
        source_id=f"SOURCE:{name}",
        source_record_id=f"ROW:{name}:A",
        observation_type=GLOBAL_TYPES[name],
        unit=GLOBAL_UNITS[name],
        session_reference="PREVIOUS_CLOSE"
        if GLOBAL_TYPES[name] == "INDEX_CLOSE"
        else "CURRENT_SESSION",
        observed_at=T0,
        published_at=T1,
        available_at=T2,
        source_verified=True,
        timestamp_semantics_verified=True,
        value_unit_verified=True,
        value_verified=True,
    )
    p.update(updates)
    return X7GlobalSourceProofV1(**p)


def raw(p, **updates):
    x = dict(
        name=p.name,
        observation_type=p.observation_type,
        unit=p.unit,
        session_reference=p.session_reference,
        source_id=p.source_id,
        source_record_id=p.source_record_id,
        observed_at=p.observed_at,
        published_at=p.published_at,
        available_at=p.available_at,
        value=5.0 if p.observation_type == "BOND_YIELD" else 100.0,
        previous_value=4.9 if p.observation_type == "BOND_YIELD" else 98.0,
    )
    x.update(updates)
    return x


def adapt(p=None, *, record=None, at=NOW, age=600.0):
    p = proof() if p is None else p
    return adapt_x7_global_observation_v1(
        raw_record=raw(p) if record is None else record,
        proof=p,
        as_of=at,
        max_age_seconds=age,
    )


def batch(names=("SP500",), market="NIFTY", **updates):
    proofs = tuple(proof(name) for name in names)
    params = dict(
        market=market,
        session_id="SESSION:1",
        capture_id="CAPTURE:1",
        as_of=NOW,
        raw_records=tuple(raw(p) for p in proofs),
        proofs=proofs,
        max_age_seconds_by_name={p.name: 600 for p in proofs},
    )
    params.update(updates)
    return adapt_x7_global_batch_v1(**params)


@pytest.mark.parametrize("name", GLOBAL_TYPES)
def test_all_controlled_global_observations_have_exact_id_type_unit_and_hash(name):
    p = proof(name)
    r = adapt(p)
    assert isinstance(r, X7GlobalAdaptedObservationV1)
    assert r.observation.name == name
    assert r.observation.observation_type == GLOBAL_TYPES[name]
    assert r.observation.unit == GLOBAL_UNITS[name]
    assert r.observation.status == "AVAILABLE"
    assert r.observation.value_verified is True
    assert r.observation.source_record_id == p.source_record_id
    assert r.proof_sha256 == p.sha256()
    assert len(r.raw_record_sha256) == len(r.sha256()) == 64
    assert r.sha256() == adapt(p).sha256()


@pytest.mark.parametrize("market", MARKETS)
def test_five_market_batch_is_descriptive_not_market_specific_prediction(market):
    b = batch(("SP500", "INDIA_VIX"), market=market)
    assert isinstance(b, X7GlobalBatchV1)
    assert b.market == market and b.observations[0].observation.name == "INDIA_VIX"
    assert len(b.observations) == 2
    assert b.dependency_groups == (
        ("US_EQUITY_CLOSES", ("SP500",)),
        ("INDIA_VOLATILITY", ("INDIA_VIX",)),
    )
    assert b.independent_vote is False and b.execution_authority is False
    assert b.live_execution_eligible is False


@pytest.mark.parametrize("name", GLOBAL_TYPES)
def test_controlled_observation_rejects_identity_type_and_unit_drift(name):
    p = proof(name)
    with pytest.raises(ValueError):
        replace(
            p, observation_type="INDEX_CLOSE" if p.observation_type != "INDEX_CLOSE" else "FX_RATE"
        )
    with pytest.raises(ValueError):
        replace(p, unit="UNVERIFIED_PRICE_UNIT")


@pytest.mark.parametrize(
    "key",
    (
        "name",
        "observation_type",
        "unit",
        "session_reference",
        "source_id",
        "source_record_id",
        "observed_at",
        "published_at",
        "available_at",
    ),
)
def test_any_raw_proof_identity_or_time_mismatch_is_rejected(key):
    p = proof()
    record = raw(p)
    record[key] = T0 - timedelta(seconds=1) if key.endswith("_at") else "WRONG"
    with pytest.raises(ValueError, match="conflicts with independent"):
        adapt(p, record=record)


@pytest.mark.parametrize(
    "bad",
    (
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        -1,
        0,
        "101",
        [],
        {},
    ),
)
def test_positive_value_requires_real_finite_positive_number(bad):
    p = proof()
    with pytest.raises(ValueError):
        adapt(p, record=raw(p, value=bad))


@pytest.mark.parametrize("bad", (True, float("nan"), float("inf"), -10, 0, "600"))
def test_non_yield_previous_value_must_be_finite_positive(bad):
    p = proof()
    with pytest.raises(ValueError):
        adapt(p, record=raw(p, previous_value=bad))


def test_optional_previous_value_may_be_missing():
    p = proof()
    assert adapt(p, record=raw(p, previous_value=None)).observation.previous_value is None


@pytest.mark.parametrize("value", (-2.0, 0.0, 6.25))
def test_bond_yield_may_be_negative_zero_or_positive(value):
    p = proof("US_10Y_YIELD")
    assert adapt(p, record=raw(p, value=value)).observation.value == value


@pytest.mark.parametrize("bad", (float("nan"), float("inf"), True, "6%"))
def test_bond_yield_rejects_invalid_numeric_forms(bad):
    p = proof("US_10Y_YIELD")
    with pytest.raises(ValueError):
        adapt(p, record=raw(p, value=bad))


@pytest.mark.parametrize(
    "field",
    (
        "source_verified",
        "timestamp_semantics_verified",
        "value_unit_verified",
        "value_verified",
    ),
)
def test_proof_boolean_fields_reject_implicit_truthy_or_numeric(field):
    p = proof()
    with pytest.raises(ValueError):
        replace(p, **{field: 1})


@pytest.mark.parametrize(
    "field",
    (
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ),
)
def test_all_b1_contracts_reject_promotion_to_authority(field):
    objects = (proof(), adapt(), batch())
    for obj in objects:
        with pytest.raises(ValueError):
            replace(obj, **{field: True})


def test_immutable_records_and_source_content_hash_tampering():
    p = proof()
    r = adapt(p)
    with pytest.raises(FrozenInstanceError):
        r.observation = None
    with pytest.raises(FrozenInstanceError):
        p.source_record_id = "CHANGED"
    assert r.raw_record_sha256 != adapt(p, record=raw(p, value=100.5)).raw_record_sha256
    assert r.proof_sha256 != adapt(replace(p, value_verified=False)).proof_sha256


def test_missing_measurement_cannot_be_verified_or_fabricated():
    p = replace(proof(), value_verified=False)
    r = adapt(p, record=raw(p, value=None))
    assert r.observation.status == "UNAVAILABLE"
    assert r.observation.value is None and r.observation.value_verified is False
    with pytest.raises(ValueError, match="absent measurement"):
        adapt(proof(), record=raw(proof(), value=None))


def test_unverified_unit_or_source_stays_unverified_not_available():
    for p in (
        replace(proof(), value_verified=False, value_unit_verified=False),
        replace(proof(), source_verified=False, value_verified=False),
    ):
        r = adapt(p)
        assert r.observation.status == "UNVERIFIED"
        assert r.observation.value_verified is False


def test_source_verification_cannot_overrule_unknown_timestamp_semantics():
    with pytest.raises(ValueError):
        replace(proof(), timestamp_semantics_verified=False)
    with pytest.raises(ValueError):
        replace(proof(), published_at=None, available_at=None)
    with pytest.raises(ValueError):
        replace(proof(), available_at=None)


def test_future_observation_publication_and_availability_each_fail_closed():
    for field in ("observed_at", "published_at", "available_at"):
        p = proof()
        time = NOW + timedelta(seconds=10)
        if field == "observed_at":
            p = replace(p, observed_at=time, published_at=time, available_at=time)
        elif field == "published_at":
            p = replace(p, published_at=time, available_at=time)
        else:
            p = replace(p, available_at=time)
        with pytest.raises(ValueError, match="future/unavailable"):
            adapt(p)


def test_stale_row_retains_values_without_becoming_available():
    p = proof()
    r = adapt(p, age=10)
    assert r.observation.status == "STALE"
    assert r.observation.value == 100.0
    assert r.observation.value_verified is True


def test_previous_close_is_not_reclassified_as_live_futures():
    p = proof("SP500")
    assert adapt(p).observation.session_reference == "PREVIOUS_CLOSE"
    with pytest.raises(ValueError):
        replace(p, observation_type="INDEX_FUTURE")
    with pytest.raises(ValueError, match="conflicts with independent"):
        adapt(p, record=raw(p, session_reference="CURRENT_SESSION"))


def test_global_vix_stays_observed_annualized_percentage_not_iv_or_direction():
    p = proof("INDIA_VIX")
    r = adapt(p, record=raw(p, value=16.7))
    assert r.observation.unit == "PERCENT_ANNUALIZED"
    assert r.observation.value == 16.7
    assert "direction" not in r.observation.__dataclass_fields__


def test_explicit_independent_freshness_budgets_support_overnight_close_vs_vix():
    b = batch(
        ("SP500", "INDIA_VIX"),
        max_age_seconds_by_name={"SP500": 10000, "INDIA_VIX": 30},
    )
    assert {r.observation.name: r.observation.status for r in b.observations} == {
        "INDIA_VIX": "STALE",
        "SP500": "AVAILABLE",
    }


def test_exact_complete_group_registry_no_independent_votes_or_double_count():
    b = batch(tuple(GLOBAL_TYPES))
    assert len(b.observations) == 14
    assert b.dependency_groups == (
        ("GIFT_INDEX_FUTURE", ("GIFT_NIFTY",)),
        ("US_EQUITY_CLOSES", ("SP500", "NASDAQ", "DOW_JONES")),
        ("ASIAN_EQUITY_CLOSES", ("NIKKEI_225", "HANG_SENG", "SHANGHAI_COMPOSITE")),
        ("CRUDE_BENCHMARKS", ("BRENT_CRUDE", "WTI_CRUDE")),
        ("FX_CONTEXT", ("DXY", "USD_INR")),
        ("BOND_YIELDS", ("US_10Y_YIELD", "INDIA_10Y_YIELD")),
        ("INDIA_VOLATILITY", ("INDIA_VIX",)),
    )
    with pytest.raises(ValueError):
        replace(b, dependency_groups=(("UNCONTROLLED", ("SP500",)),))


def test_batch_is_order_invariant_after_exact_source_binding():
    names = ("SP500", "INDIA_VIX", "GIFT_NIFTY")
    forward = batch(names)
    backward = batch(tuple(reversed(names)))
    assert forward.sha256() == backward.sha256()
    assert forward.input_sha256 == backward.input_sha256


def test_batch_rejects_duplicate_name_and_source_record():
    a = proof("SP500")
    with pytest.raises(ValueError, match="unique global names"):
        batch(raw_records=(raw(a), raw(a)), proofs=(a, a))
    b = proof("NASDAQ", source_record_id=a.source_record_id)
    with pytest.raises(ValueError, match="cannot be repeated"):
        batch(
            raw_records=(raw(a), raw(b)),
            proofs=(a, b),
            max_age_seconds_by_name={"SP500": 600, "NASDAQ": 600},
        )


def test_batch_rejects_unproven_second_row_without_silently_dropping_it():
    p = proof()
    q = proof("INDIA_VIX", value_verified=False)
    b = batch(
        names=("SP500", "INDIA_VIX"),
        raw_records=(raw(p), raw(q)),
        proofs=(p, q),
    )
    assert len(b.observations) == 2
    assert {row.observation.name: row.observation.status for row in b.observations} == {
        "INDIA_VIX": "UNVERIFIED",
        "SP500": "AVAILABLE",
    }


def test_batch_rejects_mismatched_counts_and_missing_budget():
    p = proof()
    with pytest.raises(ValueError):
        batch(proofs=())
    with pytest.raises(ValueError):
        batch(max_age_seconds_by_name={})
    with pytest.raises(ValueError):
        batch(max_age_seconds_by_name={"SP500": 600, "DXY": 600})
    with pytest.raises(ValueError):
        batch(raw_records=(raw(p),), proofs=(p, p))


@pytest.mark.parametrize("bad", (None, 0, -1, float("nan"), float("inf"), "600", True))
def test_explicit_freshness_budget_rejects_unsafe_values(bad):
    with pytest.raises(ValueError):
        adapt(age=bad)


def test_batch_rejects_wrong_market_and_unverified_record_future():
    with pytest.raises(ValueError):
        batch(market="SILVERM")
    with pytest.raises(ValueError):
        batch(as_of=datetime(2026, 10, 1, 8, 0))
    p = proof(source_verified=False, value_verified=False)
    p = replace(p, available_at=NOW + timedelta(seconds=1))
    with pytest.raises(ValueError, match="future/unavailable"):
        adapt(p)


def test_global_rows_reconnect_to_x7_a_capture_and_validation():
    b = batch(("SP500", "INDIA_VIX"))
    c = X7ContextCaptureV1(
        market=b.market,
        session_id=b.session_id,
        capture_id=b.capture_id,
        as_of=b.as_of,
        global_observations=tuple(row.observation for row in b.observations),
        institutional_flows=(),
        scheduled_events=(),
        capture_verified=True,
        point_in_time_verified=True,
        historical_retrieval=False,
    )
    v = validate_x7_context_v1(
        c,
        global_max_age_seconds=600,
        institutional_max_age_seconds=600,
        event_max_age_seconds=600,
    )
    assert v.global_status == "AVAILABLE" and v.status == "PARTIAL"
    assert v.source_capture_sha256 == c.sha256()


def test_unverified_row_cannot_be_promoted_to_point_in_time_capture():
    b = batch(("SP500",))
    assert b.observations[0].observation.status == "AVAILABLE"
    p = proof(source_verified=False, value_verified=False)
    q = adapt(p)
    with pytest.raises(ValueError):
        X7ContextCaptureV1(
            market="NIFTY",
            session_id="S",
            capture_id="C",
            as_of=NOW,
            global_observations=(q.observation,),
            institutional_flows=(),
            scheduled_events=(),
            capture_verified=True,
            point_in_time_verified=True,
            historical_retrieval=False,
        )


def test_raw_record_rejects_extra_fields_missing_fields_or_string_timestamps():
    p = proof()
    with pytest.raises(ValueError):
        adapt(p, record={**raw(p), "symboltoken": "123"})
    truncated = raw(p)
    del truncated["available_at"]
    with pytest.raises(ValueError):
        adapt(p, record=truncated)
    with pytest.raises(ValueError):
        adapt(p, record=raw(p, observed_at=T0.isoformat()))


def test_raw_provider_cannot_infer_or_transform_units_automatically():
    vix = proof("INDIA_VIX")
    with pytest.raises(ValueError):
        adapt(vix, record=raw(vix, unit="DECIMAL_ANNUALIZED"))
    with pytest.raises(ValueError):
        adapt(vix, record=raw(vix, value="16.7"))
    with pytest.raises(ValueError):
        replace(vix, value_unit_verified=False)


def test_static_authority_scan_covers_new_x7_modules():
    root = Path(__file__).resolve().parents[1]
    for path in sorted((root / "services/x7").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                names = []
            assert not any(
                name == blocked or name.startswith(blocked + ".")
                for blocked in (
                    "fyers_apiv3",
                    "SmartApi",
                    "services.broker",
                    "services.execution",
                    "services.paper_orchestration",
                    "services.trading",
                    "services.risk",
                    "requests",
                    "httpx",
                    "socket",
                    "subprocess",
                    "src.mcx",
                )
                for name in names
            )
            if isinstance(node, ast.Call):
                method = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else (node.func.id if isinstance(node.func, ast.Name) else "")
                )
                assert method not in {
                    "place_order",
                    "placeOrder",
                    "submit_order",
                    "send_order",
                    "modifyOrder",
                    "cancelOrder",
                    "execute_trade",
                }

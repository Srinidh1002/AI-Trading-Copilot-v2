"""X7-B2 institutional cash-flow adapter: source, temporal and authority gates."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from services.x7.contracts_v1 import (
    X7ContextCaptureV1,
    canonical_sha256,
)
from services.x7.input_validation_v1 import validate_x7_context_v1
from services.x7.institutional_adapter_v1 import (
    X7InstitutionalSourceProofV1,
    adapt_x7_institutional_batch_v1,
    adapt_x7_institutional_flow_v1,
)

T0 = datetime(2026, 10, 1, 11, 0, tzinfo=UTC)
T1 = T0 + timedelta(seconds=15)
T2 = T1 + timedelta(seconds=15)
NOW = T2 + timedelta(seconds=35)


def proof(**changes):
    values = dict(
        trading_date=date(2026, 10, 1),
        applicable_markets=("NIFTY", "SENSEX"),
        flow_unit="CRORE_INR",
        source_id="INSTITUTIONAL_PUBLISHER",
        source_record_id="CASH_FLOW_2026_10_01",
        observed_at=T0,
        published_at=T1,
        available_at=T2,
        publication_state="FINAL",
        source_verified=True,
        timestamp_semantics_verified=True,
        value_unit_verified=True,
        values_verified=True,
    )
    values.update(changes)
    return X7InstitutionalSourceProofV1(**values)


def record(p=None, **changes):
    p = p or proof()
    values = {
        key: getattr(p, key)
        for key in (
            "trading_date",
            "applicable_markets",
            "flow_unit",
            "source_id",
            "source_record_id",
            "observed_at",
            "published_at",
            "available_at",
            "publication_state",
        )
    }
    values.update(fii_net=-215.25, dii_net=112.75)
    values.update(changes)
    return values


def adapt(p=None, raw=None, *, as_of=NOW, max_age_seconds=600):
    p = p or proof()
    return adapt_x7_institutional_flow_v1(
        raw_record=record(p) if raw is None else raw,
        proof=p,
        as_of=as_of,
        max_age_seconds=max_age_seconds,
    )


def batch(ps=None, rs=None, market="NIFTY", *, as_of=NOW, max_age_seconds=600):
    ps = (proof(),) if ps is None else ps
    rs = tuple(record(p) for p in ps) if rs is None else rs
    return adapt_x7_institutional_batch_v1(
        market=market,
        session_id="INDEX_2026_10_01",
        capture_id="CAPTURE_INSTITUTIONAL_A",
        as_of=as_of,
        raw_records=rs,
        proofs=ps,
        max_age_seconds=max_age_seconds,
    )


@pytest.mark.parametrize("market", ("NIFTY", "SENSEX"))
@pytest.mark.parametrize(
    "fii,dii",
    (
        (-215.25, 112.75),
        (0, 0),
        (0, -5),
        (-5, 0),
        (1.25, -1.25),
        (-123456.0, 123456.0),
        (None, 5),
        (5, None),
        (None, 0),
        (0, None),
        (None, None),
    ),
)
def test_exact_index_values_and_missingness(market, fii, dii):
    p = proof(values_verified=not (fii is None and dii is None))
    row = record(p, fii_net=fii, dii_net=dii)
    b = batch(ps=(p,), rs=(row,), market=market)
    o = b.flows[0]
    assert (o.flow.fii_net, o.flow.dii_net) == (fii, dii)
    assert o.flow.flow_unit == "CRORE_INR"
    assert o.flow.status == ("UNAVAILABLE" if fii is None and dii is None else "AVAILABLE")
    assert o.data_completeness == (
        "UNAVAILABLE"
        if fii is None and dii is None
        else "PARTIAL"
        if fii is None or dii is None
        else "COMPLETE"
    )
    assert b.market == market
    assert not b.independent_vote and not b.live_execution_eligible


@pytest.mark.parametrize(
    "invalid", (float("nan"), float("inf"), -float("inf"), True, False, "5", [], {})
)
@pytest.mark.parametrize("field", ("fii_net", "dii_net"))
def test_invalid_numbers_rejected(field, invalid):
    with pytest.raises((TypeError, ValueError)):
        adapt(raw=record(proof(), **{field: invalid}))


@pytest.mark.parametrize(
    "field,value",
    (
        ("flow_unit", "RUPEES"),
        ("flow_unit", "CONTRACTS"),
        ("flow_unit", "NOTIONAL_CRORE_INR"),
        ("applicable_markets", ("CRUDEOILM",)),
        ("applicable_markets", ("GOLDM",)),
        ("applicable_markets", ("NATGASMINI",)),
        ("applicable_markets", ("SENSEX", "NIFTY")),
        ("applicable_markets", ("NIFTY", "NIFTY")),
        ("source_id", ""),
        ("source_record_id", ""),
        ("publication_state", "INFERRED"),
        ("observed_at", datetime(2026, 10, 1, 11, 0)),
        ("observed_at", T0 - timedelta(days=2)),
        ("published_at", T0 - timedelta(seconds=1)),
        ("available_at", T0),
        ("source_verified", 1),
        ("value_unit_verified", 1),
        ("timestamp_semantics_verified", 1),
        ("values_verified", 1),
    ),
)
def test_invalid_source_proof_rejected(field, value):
    with pytest.raises((TypeError, ValueError)):
        proof(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    (
        ("trading_date", date(2026, 9, 30)),
        ("applicable_markets", ("NIFTY",)),
        ("flow_unit", "RUPEES"),
        ("source_id", "SOME_OTHER_PUBLISHER"),
        ("source_record_id", "ANOTHER_RECORD"),
        ("observed_at", T0 + timedelta(seconds=1)),
        ("published_at", T2),
        ("available_at", NOW),
        ("publication_state", "PROVISIONAL"),
    ),
)
def test_raw_proof_identity_mismatch_rejected(field, value):
    with pytest.raises((TypeError, ValueError), match="conflicts"):
        adapt(raw=record(proof(), **{field: value}))


@pytest.mark.parametrize(
    "field",
    ("source_verified", "timestamp_semantics_verified", "value_unit_verified", "values_verified"),
)
def test_missing_attestation_does_not_promote_final_evidence(field):
    changes = {field: False, "values_verified": False}
    if field == "timestamp_semantics_verified":
        changes["source_verified"] = False
    p = proof(**changes)
    a = adapt(p)
    assert a.flow.status == "UNVERIFIED"
    assert a.flow.values_verified is False
    assert a.flow.fii_net == -215.25
    assert a.data_completeness == "COMPLETE"


@pytest.mark.parametrize("field", ("observed_at", "published_at", "available_at"))
def test_future_data_rejected_even_when_verified(field):
    p = proof(**{field: NOW + timedelta(seconds=1)}) if field == "available_at" else None
    if field == "observed_at":
        p = proof(
            observed_at=NOW + timedelta(seconds=1),
            published_at=NOW + timedelta(seconds=2),
            available_at=NOW + timedelta(seconds=3),
        )
    if field == "published_at":
        p = proof(published_at=NOW + timedelta(seconds=1), available_at=NOW + timedelta(seconds=2))
    with pytest.raises(ValueError, match="Future|future"):
        adapt(p)


@pytest.mark.parametrize("age", (1, 5, 10, 35, 60, 600))
def test_staleness_must_use_explicit_budget(age):
    a = adapt(max_age_seconds=age)
    elapsed = (NOW - T0).total_seconds()
    assert a.flow.status == ("STALE" if elapsed > age else "AVAILABLE")
    assert a.flow.values_verified


@pytest.mark.parametrize("bad", (0, -1, float("nan"), float("inf"), True, "60", None))
def test_invalid_age_budget_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        adapt(max_age_seconds=bad)


@pytest.mark.parametrize("publication", ("FINAL", "PROVISIONAL", "UNAVAILABLE"))
@pytest.mark.parametrize("verified", (True, False))
def test_publication_state_not_promoted(publication, verified):
    p = proof(publication_state=publication, values_verified=verified)
    a = adapt(p)
    assert a.flow.publication_state == publication
    assert a.flow.status == ("AVAILABLE" if publication == "FINAL" and verified else "UNVERIFIED")
    assert a.flow.values_verified == (publication == "FINAL" and verified)
    assert a.flow.fii_net == -215.25


def test_caller_source_proof_does_not_authenticate_a_publisher():
    p = proof(source_id="TEST_FIXTURE_ASSERTION")
    a = adapt(p)
    assert a.flow.source_id == "TEST_FIXTURE_ASSERTION"
    assert a.flow.status == "AVAILABLE"  # Contract proof only; NOT external authentication.


@pytest.mark.parametrize("market", ("CRUDEOILM", "GOLDM", "NATGASMINI", "BANKNIFTY", ""))
def test_institutional_cash_batch_never_assigned_to_other_markets(market):
    with pytest.raises(ValueError):
        batch(market=market)


@pytest.mark.parametrize("market", ("NIFTY", "SENSEX"))
def test_proof_market_applicability_strict(market):
    other = "SENSEX" if market == "NIFTY" else "NIFTY"
    p = proof(applicable_markets=(other,))
    with pytest.raises(ValueError):
        batch(ps=(p,), market=market)


def test_batch_sorted_by_trading_date_but_rejects_duplicate_capture_day():
    p1 = proof(trading_date=date(2026, 10, 1), source_record_id="DAY1")
    p0 = proof(trading_date=date(2026, 9, 30), source_record_id="DAY0")
    b = batch(ps=(p1, p0))
    assert tuple(x.flow.trading_date for x in b.flows) == (p0.trading_date, p1.trading_date)
    assert b.sha256() == batch(ps=(p0, p1)).sha256()
    with pytest.raises(ValueError, match="Duplicate"):
        batch(ps=(p1, replace(p1, source_record_id="DAY1_NEW")))


def test_duplicate_source_record_and_mismatched_record_count_rejected():
    p1 = proof()
    p2 = replace(p1, trading_date=date(2026, 9, 30))
    with pytest.raises(ValueError, match="Duplicate"):
        batch(ps=(p1, p2))
    with pytest.raises(ValueError, match="needs its own proof"):
        batch(ps=(p1,), rs=())


def test_empty_batch_is_explicitly_empty_not_a_fake_flow():
    b = batch(ps=(), rs=())
    assert b.flows == ()
    assert b.input_sha256 and b.market == "NIFTY"


def test_batch_hashes_are_deterministic_and_react_to_value_provenance_and_age():
    p = proof()
    a = batch(ps=(p,))
    assert a.sha256() == batch(ps=(p,)).sha256()
    assert a.input_sha256 == batch(ps=(p,)).input_sha256
    assert a.input_sha256 != batch(ps=(p,), max_age_seconds=900).input_sha256
    assert a.input_sha256 != batch(ps=(p,), rs=(record(p, fii_net=-99),)).input_sha256
    other = replace(p, source_record_id="OTHER")
    assert a.input_sha256 != batch(ps=(other,)).input_sha256
    assert a.flows[0].raw_record_sha256 == canonical_sha256(record(p))
    assert a.flows[0].proof_sha256 == p.sha256()


def test_typed_proof_and_raw_record_are_required():
    with pytest.raises((TypeError, ValueError)):
        adapt_x7_institutional_flow_v1(
            raw_record="fake", proof=proof(), as_of=NOW, max_age_seconds=600
        )
    with pytest.raises((TypeError, ValueError)):
        adapt_x7_institutional_flow_v1(
            raw_record=record(), proof={}, as_of=NOW, max_age_seconds=600
        )
    with pytest.raises((TypeError, ValueError)):
        adapt_x7_institutional_flow_v1(
            raw_record={**record(), "extra": 42}, proof=proof(), as_of=NOW, max_age_seconds=600
        )
    with pytest.raises((TypeError, ValueError)):
        adapt_x7_institutional_flow_v1(
            raw_record={k: v for k, v in record().items() if k != "fii_net"},
            proof=proof(),
            as_of=NOW,
            max_age_seconds=600,
        )


def test_proof_flags_are_dependency_checked():
    with pytest.raises(ValueError):
        proof(source_verified=False, values_verified=True)
    with pytest.raises(ValueError):
        proof(timestamp_semantics_verified=False)
    with pytest.raises(ValueError):
        proof(value_unit_verified=False)
    with pytest.raises(ValueError):
        proof(published_at=None)
    with pytest.raises(ValueError):
        proof(available_at=None)


def test_bad_as_of_is_rejected():
    with pytest.raises(TypeError):
        adapt(as_of=datetime(2026, 10, 1, 11, 0))
    with pytest.raises(ValueError):
        batch(as_of=NOW - timedelta(hours=10))


def test_source_and_adapted_objects_are_frozen():
    a = adapt()
    with pytest.raises(FrozenInstanceError):
        a.source_record_id = "REPLACED"
    with pytest.raises(FrozenInstanceError):
        a.flow.fii_net = 999
    with pytest.raises(FrozenInstanceError):
        a.flow.source_id = "REPLACED"
    with pytest.raises(FrozenInstanceError):
        a.as_of = NOW


def test_no_direct_trading_authority_and_no_independent_vote():
    p = proof()
    a = adapt(p)
    b = batch()
    for item in (p, a, b, a.flow):
        assert item.data_only is True
        assert item.independent_vote is False
        for field in (
            "execution_authority",
            "risk_authority",
            "position_authority",
            "certification_authority",
            "live_execution_eligible",
        ):
            assert getattr(item, field) is False
    for item in (p, a, b):
        for field in (
            "execution_authority",
            "risk_authority",
            "position_authority",
            "certification_authority",
            "live_execution_eligible",
            "independent_vote",
        ):
            with pytest.raises(ValueError):
                replace(item, **{field: True})


def test_context_validation_retains_finality_and_partial_completeness():
    p = proof()
    a = adapt(p, raw=record(p, dii_net=None))
    assert a.data_completeness == "PARTIAL"
    capture = X7ContextCaptureV1(
        market="NIFTY",
        session_id="SESSION",
        capture_id="CAPTURE",
        as_of=NOW,
        global_observations=(),
        institutional_flows=(a.flow,),
        scheduled_events=(),
        capture_verified=True,
        point_in_time_verified=True,
        historical_retrieval=False,
    )
    v = validate_x7_context_v1(
        capture,
        global_max_age_seconds=600,
        institutional_max_age_seconds=600,
        event_max_age_seconds=600,
    )
    assert v.institutional_status == "AVAILABLE"  # At least one verified field.
    assert v.status == "PARTIAL"  # Other families are absent.
    assert a.data_completeness == "PARTIAL"  # DII is *not* silently zero.


def test_provisional_facts_not_promoted_by_context_validation():
    p = proof(publication_state="PROVISIONAL")
    a = adapt(p)
    capture = X7ContextCaptureV1(
        market="NIFTY",
        session_id="SESSION",
        capture_id="CAPTURE",
        as_of=NOW,
        global_observations=(),
        institutional_flows=(a.flow,),
        scheduled_events=(),
        capture_verified=True,
        point_in_time_verified=True,
        historical_retrieval=False,
    )
    v = validate_x7_context_v1(
        capture,
        global_max_age_seconds=600,
        institutional_max_age_seconds=600,
        event_max_age_seconds=600,
    )
    assert v.institutional_status == "UNAVAILABLE"
    assert v.status == "UNAVAILABLE"


def test_static_authority_scan_all_x7_sources():
    root = Path(__file__).resolve().parents[1] / "services" / "x7"
    blocked = (
        "fyers_apiv3",
        "SmartApi",
        "services.broker",
        "services.execution",
        "services.paper_orchestration",
        "services.paper_trading",
        "services.trading",
        "services.risk",
        "subprocess",
        "socket",
        "requests",
        "httpx",
    )
    scripts = tuple(sorted(root.glob("*.py")))
    assert {
        "__init__.py",
        "contracts_v1.py",
        "input_validation_v1.py",
        "global_adapter_v1.py",
        "institutional_adapter_v1.py",
    }.issubset({script.name for script in scripts})
    for script in scripts:
        tree = ast.parse(script.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = (item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                names = (node.module or "",)
            else:
                names = ()
            for name in names:
                assert not any(name == b or name.startswith(b + ".") for b in blocked)
            if isinstance(node, ast.Call):
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else ""
                )
                assert name not in {
                    "place_order",
                    "placeOrder",
                    "submit_order",
                    "modifyOrder",
                    "cancelOrder",
                    "execute_trade",
                }


def test_public_contract_shape_has_no_trade_action_or_position_sizing():
    for obj in (proof(), adapt(), batch()):
        names = set(asdict(obj))
        assert not (
            names
            & {
                "action",
                "side",
                "strike_to_buy",
                "quantity",
                "confidence",
                "entry",
                "stop_loss",
                "target",
                "lot_size",
                "signal",
            }
        )

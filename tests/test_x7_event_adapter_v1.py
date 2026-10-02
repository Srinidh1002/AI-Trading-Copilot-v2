"""Offline five-market X7-B3 calendar-adapter tests and authority isolation."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from services.x7.contracts_v1 import (
    EVENT_CATEGORIES,
    MARKETS,
    X7ContextCaptureV1,
    canonical_sha256,
)
from services.x7.event_adapter_v1 import (
    CONTRACT_EVENTS,
    EXPIRY_EVENTS,
    SESSION_EVENTS,
    X7EventSourceProofV1,
    adapt_x7_scheduled_event_batch_v1,
    adapt_x7_scheduled_event_v1,
)
from services.x7.input_validation_v1 import validate_x7_context_v1

T0 = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
PUB = T0 + timedelta(minutes=5)
AVAIL = T0 + timedelta(minutes=10)
NOW = T0 + timedelta(minutes=30)
EVENT = T0 + timedelta(days=1)


def proof(*, category="RBI_POLICY", state="CONFIRMED", market="NIFTY", **changes):
    values = dict(
        event_id=f"{category}:A",
        category=category,
        scheduled_at=EVENT,
        affected_markets=(market,) if category in CONTRACT_EVENTS else MARKETS,
        severity="HIGH",
        source_id="VERIFIED_EVENT_CALENDAR",
        source_record_id=f"RECORD:{category}:A",
        observed_at=T0,
        published_at=PUB,
        available_at=AVAIL,
        schedule_state=state,
        bound_contract_id=f"EXACT:{market}:OCT" if category in CONTRACT_EVENTS else None,
        bound_contract_expiry=EVENT.date() if category in CONTRACT_EVENTS else None,
        source_verified=True,
        timestamp_semantics_verified=True,
        schedule_verified=state == "CONFIRMED",
        calendar_reference_verified=category in SESSION_EVENTS and state == "CONFIRMED",
        contract_binding_verified=category in CONTRACT_EVENTS and state == "CONFIRMED",
    )
    values.update(changes)
    return X7EventSourceProofV1(**values)


def raw(p, **changes):
    values = {
        key: getattr(p, key)
        for key in (
            "event_id",
            "category",
            "scheduled_at",
            "affected_markets",
            "severity",
            "source_id",
            "source_record_id",
            "observed_at",
            "published_at",
            "available_at",
            "schedule_state",
            "bound_contract_id",
            "bound_contract_expiry",
        )
    }
    values.update(changes)
    return values


def adapt(p=None, *, record=None, as_of=NOW, max_age_seconds=3600):
    p = p or proof()
    return adapt_x7_scheduled_event_v1(
        raw_record=raw(p) if record is None else record,
        proof=p,
        as_of=as_of,
        max_age_seconds=max_age_seconds,
    )


def batch(ps=None, rs=None, *, market="NIFTY", as_of=NOW, max_age_seconds=3600):
    ps = (proof(market=market),) if ps is None else ps
    rs = tuple(raw(p) for p in ps) if rs is None else rs
    return adapt_x7_scheduled_event_batch_v1(
        market=market,
        session_id="S:2026-10-02",
        capture_id="C:OCT02",
        as_of=as_of,
        raw_records=rs,
        proofs=ps,
        max_age_seconds=max_age_seconds,
    )


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("category", sorted(EVENT_CATEGORIES))
def test_all_five_markets_each_supported_event_category(market, category):
    p = proof(category=category, market=market)
    a = adapt(p)
    b = batch(ps=(p,), market=market)
    assert a.event.category == category
    assert a.event.status == "AVAILABLE" and a.event.confirmed is True
    assert b.events == (a,) and b.market == market
    assert b.input_sha256 and len(b.input_sha256) == 64
    assert not a.independent_vote and not b.live_execution_eligible


@pytest.mark.parametrize("state", ("TENTATIVE", "CANCELLED", "POSTPONED", "UNAVAILABLE"))
@pytest.mark.parametrize("category", ("RBI_POLICY", "CPI", "EXCHANGE_HOLIDAY", "WEEKLY_EXPIRY"))
def test_nonconfirmed_schedule_never_available(state, category):
    p = proof(category=category, state=state)
    a = adapt(p)
    assert a.schedule_state == state
    assert a.event.status in {"UNVERIFIED", "UNAVAILABLE"}
    assert a.event.confirmed is False
    assert f"SCHEDULE_{state}" in a.reasons
    assert len(a.sha256()) == 64


@pytest.mark.parametrize(
    "field,bad",
    (
        ("event_id", " "),
        ("source_id", ""),
        ("source_record_id", " "),
        ("category", "BREAKING_NEWS"),
        ("severity", "CRITICAL"),
        ("schedule_state", "RUMORED"),
        ("affected_markets", ()),
        ("affected_markets", ("SILVERM",)),
        ("affected_markets", ("SENSEX", "NIFTY")),
        ("affected_markets", ("NIFTY", "NIFTY")),
        ("affected_markets", ["NIFTY"]),
        ("scheduled_at", EVENT.replace(tzinfo=None)),
        ("observed_at", T0.replace(tzinfo=None)),
        ("published_at", T0 - timedelta(seconds=1)),
        ("published_at", PUB.replace(tzinfo=None)),
        ("available_at", PUB - timedelta(seconds=1)),
        ("available_at", AVAIL.replace(tzinfo=None)),
        ("source_verified", 1),
        ("timestamp_semantics_verified", "yes"),
        ("schedule_verified", None),
        ("calendar_reference_verified", 0),
        ("contract_binding_verified", 1),
    ),
)
def test_rejects_invalid_proof(field, bad):
    with pytest.raises((ValueError, TypeError)):
        proof(**{field: bad})


@pytest.mark.parametrize(
    "field,bad",
    (
        ("event_id", "OTHER"),
        ("category", "GDP"),
        ("scheduled_at", EVENT + timedelta(hours=1)),
        ("affected_markets", ("NIFTY",)),
        ("severity", "LOW"),
        ("source_id", "UNRELATED_SOURCE"),
        ("source_record_id", "RECORD:FAKE"),
        ("observed_at", T0 + timedelta(seconds=1)),
        ("published_at", PUB + timedelta(seconds=1)),
        ("available_at", AVAIL + timedelta(seconds=1)),
        ("schedule_state", "CANCELLED"),
        ("bound_contract_id", "WRONG"),
        ("bound_contract_expiry", date(2026, 10, 9)),
    ),
)
def test_raw_and_proof_exact_identity_binding(field, bad):
    p = proof()
    # Non-contract fields are checked too, even if the value is otherwise valid.
    with pytest.raises(ValueError, match="conflicts"):
        adapt(p, record=raw(p, **{field: bad}))


@pytest.mark.parametrize("field", ("observed_at", "published_at", "available_at"))
def test_future_calendar_information_does_not_leak_into_replay(field):
    future = NOW + timedelta(minutes=1)
    if field == "observed_at":
        p = proof(observed_at=future, published_at=future, available_at=future)
    elif field == "published_at":
        p = proof(published_at=future, available_at=future)
    else:
        p = proof(available_at=future)
    with pytest.raises(ValueError, match="Future|not-yet-published"):
        adapt(p)


@pytest.mark.parametrize("bad", (0, -1, float("nan"), float("inf"), True, "3600"))
def test_explicit_freshness_budget_required(bad):
    with pytest.raises(ValueError):
        adapt(max_age_seconds=bad)


@pytest.mark.parametrize("category", sorted(EXPIRY_EVENTS))
def test_expiry_must_bind_one_market_and_exact_ist_date(category):
    p = proof(category=category)
    assert adapt(p).event.status == "AVAILABLE"
    with pytest.raises(ValueError):
        replace(p, bound_contract_expiry=date(2026, 10, 4))
    with pytest.raises(ValueError):
        replace(p, affected_markets=("NIFTY", "SENSEX"))
    with pytest.raises(ValueError):
        replace(p, bound_contract_id=None)


def test_expiry_uses_ist_date_not_naive_utc_calendar_date():
    p = proof(category="MONTHLY_EXPIRY", scheduled_at=datetime(2026, 10, 2, 22, 0, tzinfo=UTC))
    assert p.scheduled_at.date() != p.bound_contract_expiry
    assert (
        p.scheduled_at.astimezone(
            __import__("datetime").timezone(timedelta(hours=5, minutes=30))
        ).date()
        == p.bound_contract_expiry
    )


def test_rollover_expiry_not_auto_assumed_or_rewritten():
    p = proof(category="ROLLOVER", bound_contract_expiry=date(2026, 10, 8))
    assert adapt(p).event.category == "ROLLOVER"
    with pytest.raises(ValueError):
        replace(p, bound_contract_expiry=date(2026, 10, 1))


@pytest.mark.parametrize("category", tuple(sorted(SESSION_EVENTS)))
def test_session_fact_cannot_claim_exchange_open_close_authority(category):
    p = proof(category=category, calendar_reference_verified=False)
    a = adapt(p)
    assert a.event.status == "UNVERIFIED"
    assert not a.event.confirmed
    assert "CANONICAL_SESSION_REFERENCE_UNVERIFIED" in a.reasons
    assert "session_override" not in asdict(a)
    assert adapt(replace(p, calendar_reference_verified=True)).event.status == "AVAILABLE"


@pytest.mark.parametrize("category", tuple(sorted(CONTRACT_EVENTS)))
def test_unverified_contract_binding_is_not_confirmed(category):
    p = proof(category=category, contract_binding_verified=False)
    a = adapt(p)
    assert a.event.status == "UNVERIFIED" and not a.event.confirmed
    assert "CONTRACT_EXPIRY_OR_ROLLOVER_BINDING_UNVERIFIED" in a.reasons


def test_stale_confirmed_fact_retains_publisher_fact_but_is_unavailable():
    a = adapt(max_age_seconds=1)
    assert a.event.status == "STALE" and a.event.confirmed
    assert a.schedule_state == "CONFIRMED"
    assert "STALE_CALENDAR_RECORD" in a.reasons


def test_missing_publication_attestation_never_inferred():
    p = proof(
        source_verified=False,
        timestamp_semantics_verified=False,
        schedule_verified=False,
        published_at=None,
        available_at=None,
    )
    a = adapt(p)
    assert a.event.status == "UNVERIFIED" and not a.event.confirmed
    assert a.event.published_at is None and a.event.available_at is None


def test_timestamp_or_schedule_verification_missing_is_not_promoted():
    p = proof(source_verified=False, timestamp_semantics_verified=False, schedule_verified=False)
    assert adapt(p).event.status == "UNVERIFIED"
    p = proof(schedule_verified=False)
    assert adapt(p).event.status == "UNVERIFIED"


def test_unknown_severity_remains_unverified_without_inference():
    p = proof(severity="UNKNOWN", schedule_verified=False)
    a = adapt(p)
    assert "SEVERITY_UNAVAILABLE" in a.reasons
    assert a.event.status == "UNVERIFIED"


def test_immutable_provenance_hashes_and_changes():
    p = proof()
    a = adapt(p)
    b = batch()
    with pytest.raises(FrozenInstanceError):
        a.schedule_state = "CANCELLED"
    with pytest.raises(FrozenInstanceError):
        p.source_id = "FORGED"
    assert a.raw_record_sha256 == canonical_sha256(raw(p))
    assert a.proof_sha256 == p.sha256()
    assert a.sha256() == adapt(p).sha256()
    assert a.sha256() != adapt(replace(p, event_id="OTHER"), record=None).sha256()
    assert b.sha256() == batch().sha256()
    with pytest.raises(ValueError):
        replace(b, input_sha256="0" * 64)


def test_ordered_batch_and_input_hash_are_independent_of_order():
    p = proof()
    q = proof(category="CPI", scheduled_at=EVENT + timedelta(hours=1))
    b1 = batch(ps=(p, q))
    b2 = batch(ps=(q, p))
    assert b1 == b2 and b1.sha256() == b2.sha256()
    assert tuple(x.event.event_id for x in b1.events) == (p.event_id, q.event_id)


def test_duplicate_ids_and_provenance_are_rejected():
    p = proof()
    q = replace(p, source_record_id="ANOTHER")
    with pytest.raises(ValueError, match="Duplicate scheduled-event IDs"):
        batch(ps=(p, q))
    q = replace(p, event_id="DIFFERENT")
    with pytest.raises(ValueError, match="Duplicate source-record identity"):
        batch(ps=(p, q))


@pytest.mark.parametrize("market", MARKETS)
def test_cross_market_isolation(market):
    p = proof(market="NIFTY", category="WEEKLY_EXPIRY")
    if market != "NIFTY":
        with pytest.raises(ValueError, match="does not apply"):
            batch(ps=(p,), market=market)
    else:
        assert batch(ps=(p,), market=market).market == market


def test_capture_and_existing_validation_link_exact_rows():
    p = proof()
    b = batch(ps=(p,))
    c = X7ContextCaptureV1(
        market="NIFTY",
        session_id=b.session_id,
        capture_id=b.capture_id,
        as_of=b.as_of,
        global_observations=(),
        institutional_flows=(),
        scheduled_events=tuple(x.event for x in b.events),
        capture_verified=True,
        point_in_time_verified=True,
        historical_retrieval=False,
    )
    v = validate_x7_context_v1(
        c,
        global_max_age_seconds=3600,
        institutional_max_age_seconds=3600,
        event_max_age_seconds=3600,
    )
    assert v.event_status == "AVAILABLE" and v.global_status == "UNAVAILABLE"
    assert v.status == "PARTIAL" and v.source_capture_sha256 == c.sha256()
    a = adapt(proof(state="CANCELLED"))
    c2 = replace(c, scheduled_events=(a.event,))
    assert (
        validate_x7_context_v1(
            c2,
            global_max_age_seconds=3600,
            institutional_max_age_seconds=3600,
            event_max_age_seconds=3600,
        ).event_status
        == "UNAVAILABLE"
    )


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
def test_zero_authority_immutable_across_event_artifacts(field):
    for obj in (proof(), adapt(), batch()):
        with pytest.raises(ValueError):
            replace(obj, **{field: True})


@pytest.mark.parametrize("obj", (proof(), adapt(), batch()))
def test_schema_and_data_only_enforced(obj):
    with pytest.raises(ValueError):
        replace(obj, data_only=False)
    with pytest.raises(ValueError):
        replace(obj, schema_version="OTHER")


def test_exact_raw_record_shape_and_batch_cardinality():
    p = proof()
    with pytest.raises(ValueError):
        adapt(p, record={**raw(p), "BUY_CALL": True})
    truncated = raw(p)
    del truncated["event_id"]
    with pytest.raises(ValueError):
        adapt(p, record=truncated)
    with pytest.raises(ValueError):
        batch(ps=(p,), rs=())
    with pytest.raises(ValueError):
        batch(ps=[p])


def test_static_x7_authority_scan_includes_new_event_module():
    root = Path(__file__).resolve().parents[1] / "services" / "x7"
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [item.name for item in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for name in names:
                    assert not any(
                        name == blocked or name.startswith(blocked + ".")
                        for blocked in (
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
                            "src.mcx",
                        )
                    )
            if isinstance(node, ast.Call):
                method = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else ""
                )
                assert method not in {
                    "place_order",
                    "placeOrder",
                    "submit_order",
                    "modifyOrder",
                    "cancelOrder",
                    "execute_trade",
                }
    for obj in (proof(), adapt(), batch()):
        assert not any(
            field in asdict(obj)
            for field in (
                "action",
                "side",
                "strike_to_buy",
                "quantity",
                "entry",
                "stop_loss",
                "target",
                "confidence",
                "lot_size",
                "capital",
                "order_id",
                "signal",
            )
        )

"""X7-A matrix: five-market immutable external evidence and provenance gates."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from services.x7.contracts_v1 import (
    EVENT_CATEGORIES,
    GLOBAL_TYPES,
    GLOBAL_UNITS,
    MARKETS,
    X7ContextCaptureV1,
    X7GlobalObservationV1,
    X7InstitutionalFlowV1,
    X7ScheduledEventV1,
)
from services.x7.input_validation_v1 import validate_x7_context_v1

T0 = datetime(2026, 10, 1, 7, 0, tzinfo=UTC)
T1 = T0 + timedelta(minutes=1)
T2 = T0 + timedelta(minutes=2)
NOW = T0 + timedelta(minutes=5)


def global_obs(**changes):
    values = dict(
        name="SP500",
        observation_type="INDEX_CLOSE",
        unit="INDEX_POINTS",
        session_reference="PREVIOUS_CLOSE",
        source_id="EXCHANGE:SP500",
        observed_at=T0,
        published_at=T1,
        available_at=T2,
        source_verified=True,
        value=6000.0,
        value_verified=True,
        previous_value=5950.0,
        status="AVAILABLE",
        source_record_id="OBS-1",
    )
    values.update(changes)
    return X7GlobalObservationV1(**values)


def flow(**changes):
    values = dict(
        trading_date=date(2026, 10, 1),
        applicable_markets=("NIFTY", "SENSEX"),
        flow_unit="CRORE_INR",
        source_id="EXCHANGE:CASH_FLOW",
        observed_at=T0,
        published_at=T1,
        available_at=T2,
        source_verified=True,
        fii_net=0.0,
        dii_net=-150.0,
        values_verified=True,
        publication_state="FINAL",
        status="AVAILABLE",
    )
    values.update(changes)
    return X7InstitutionalFlowV1(**values)


def event(**changes):
    values = dict(
        event_id="RBI:OCT",
        category="RBI_POLICY",
        scheduled_at=NOW + timedelta(days=2),
        affected_markets=MARKETS,
        severity="HIGH",
        source_id="CALENDAR:RBI",
        observed_at=T0,
        published_at=T1,
        available_at=T2,
        source_verified=True,
        confirmed=True,
        status="AVAILABLE",
    )
    values.update(changes)
    return X7ScheduledEventV1(**values)


def capture(market="NIFTY", **changes):
    values = dict(
        market=market,
        session_id="2026-10-01:IST",
        capture_id="CAPTURE:1",
        as_of=NOW,
        global_observations=(global_obs(),),
        institutional_flows=(flow(),) if market in ("NIFTY", "SENSEX") else (),
        scheduled_events=(event(),),
        capture_verified=True,
        point_in_time_verified=True,
        historical_retrieval=False,
    )
    values.update(changes)
    return X7ContextCaptureV1(**values)


def validate(value, **budgets):
    values = dict(
        global_max_age_seconds=3600,
        institutional_max_age_seconds=3600,
        event_max_age_seconds=86400,
    )
    values.update(budgets)
    return validate_x7_context_v1(value, **values)


@pytest.mark.parametrize("market", MARKETS)
def test_five_market_contracts_and_descriptive_status(market):
    c = capture(market)
    result = validate(c)
    assert result.source_capture_sha256 == c.sha256()
    assert result.global_status == "AVAILABLE"
    assert result.event_status == "AVAILABLE"
    assert result.institutional_status == (
        "AVAILABLE" if market in ("NIFTY", "SENSEX") else "UNAVAILABLE"
    )
    assert result.status == ("AVAILABLE" if market in ("NIFTY", "SENSEX") else "PARTIAL")
    assert result.data_only is True and result.independent_vote is False
    assert result.live_execution_eligible is False


@pytest.mark.parametrize("name,kind", GLOBAL_TYPES.items())
def test_global_name_type_unit_matrix(name, kind):
    r = global_obs(name=name, observation_type=kind, unit=GLOBAL_UNITS[name])
    assert r.name == name
    with pytest.raises(ValueError):
        replace(
            r, observation_type="COMMODITY_PRICE" if kind != "COMMODITY_PRICE" else "INDEX_CLOSE"
        )
    with pytest.raises(ValueError):
        replace(r, unit="UNDECLARED_UNIT")


@pytest.mark.parametrize("category", sorted(EVENT_CATEGORIES))
def test_event_categories_are_controlled(category):
    assert event(category=category).category == category


@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), float("-inf"), True, "6000", -1.0, 0.0]
)
def test_global_bad_prices(bad):
    with pytest.raises(ValueError):
        global_obs(value=bad)


def test_bond_yields_can_be_negative_with_declared_percentage_unit():
    assert (
        global_obs(
            name="US_10Y_YIELD",
            observation_type="BOND_YIELD",
            unit="PERCENT_PER_YEAR",
            value=-0.2,
            previous_value=-0.1,
        ).value
        == -0.2
    )


@pytest.mark.parametrize(
    "changes",
    [
        dict(observed_at=T0.replace(tzinfo=None)),
        dict(published_at=T0 - timedelta(minutes=1)),
        dict(available_at=T0),
        dict(source_verified=True, published_at=None),
        dict(source_verified=True, available_at=None),
        dict(value_verified=True, source_verified=False),
        dict(value_verified=True, value=None),
        dict(source_id=" "),
        dict(status="AVAILABLE", value_verified=False),
        dict(status="AVAILABLE", source_record_id=None),
        dict(status="UNAVAILABLE", value=0.0),
        dict(status="NOT_A_STATUS"),
    ],
)
def test_global_provenance_and_status_rejections(changes):
    with pytest.raises(ValueError):
        global_obs(**changes)


@pytest.mark.parametrize("bad", ["NIFTY", "NFO", None, "", 0, 12.0])
def test_invalid_global_type_and_identity(bad):
    with pytest.raises((ValueError, TypeError)):
        global_obs(name=bad)


def test_missing_source_fields_do_not_become_verified():
    r = global_obs(
        source_verified=False,
        published_at=None,
        available_at=None,
        value=6000.0,
        value_verified=False,
        status="UNVERIFIED",
    )
    assert r.value == 6000.0 and r.value_verified is False
    with pytest.raises(ValueError):
        replace(r, status="AVAILABLE")


def test_missing_numeric_value_is_not_a_false_zero():
    r = global_obs(value=None, value_verified=False, status="UNAVAILABLE")
    assert r.value is None


@pytest.mark.parametrize("bad", ["RUPEES", "CONTRACTS", "UNKNOWN", None])
def test_cash_flow_units_must_be_explicit_crore_inr(bad):
    with pytest.raises(ValueError):
        flow(flow_unit=bad)


@pytest.mark.parametrize(
    "values",
    [
        ("NIFTY", "CRUDEOILM"),
        ("CRUDEOILM",),
        ("SENSEX", "NIFTY"),
        ("NIFTY", "NIFTY"),
        (),
        ["NIFTY"],
    ],
)
def test_cash_flow_applicability_is_index_only_unique_ordered_tuple(values):
    with pytest.raises(ValueError):
        flow(applicable_markets=values)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "0", True])
def test_institutional_signed_number_validation(bad):
    with pytest.raises(ValueError):
        flow(fii_net=bad)


@pytest.mark.parametrize(
    "changes",
    [
        dict(publication_state="PROVISIONAL"),
        dict(source_verified=False, values_verified=True),
        dict(fii_net=None, dii_net=None),
        dict(trading_date=T0),
        dict(trading_date=date(2026, 10, 2)),
        dict(status="UNAVAILABLE"),
        dict(status="UNVERIFIED"),
    ],
)
def test_institutional_invalid_available_state(changes):
    with pytest.raises(ValueError):
        flow(**changes)


def test_provisional_flow_explicitly_unverified():
    row = flow(
        publication_state="PROVISIONAL",
        values_verified=False,
        status="UNVERIFIED",
    )
    assert row.fii_net == 0 and row.dii_net == -150
    assert row.values_verified is False


def test_verified_zero_is_distinct_from_unknown():
    assert flow(fii_net=0).fii_net == 0
    assert flow(fii_net=None).fii_net is None


@pytest.mark.parametrize(
    "changes",
    [
        dict(affected_markets=()),
        dict(affected_markets=("MCX",)),
        dict(affected_markets=("GOLDM", "NIFTY")),
        dict(affected_markets=("NIFTY", "NIFTY")),
        dict(category="BREAKING_NEWS"),
        dict(scheduled_at=NOW.replace(tzinfo=None)),
        dict(confirmed=False),
        dict(severity="UNKNOWN"),
        dict(source_verified=False),
        dict(status="UNAVAILABLE"),
    ],
)
def test_event_must_have_confirmed_sourced_applicable_fact(changes):
    with pytest.raises(ValueError):
        event(**changes)


def test_tentative_event_is_not_reported_as_confirmed():
    r = event(confirmed=False, status="UNVERIFIED")
    assert r.status == "UNVERIFIED"


def test_scheduled_future_event_is_known_as_of_its_announcement():
    r = event(scheduled_at=NOW + timedelta(days=30))
    assert r.available_at < NOW < r.scheduled_at
    assert validate(capture(scheduled_events=(r,))).event_status == "AVAILABLE"


@pytest.mark.parametrize("market", ["GOLDM", "NATGASMINI", "CRUDEOILM"])
def test_equity_cash_flows_cannot_be_silently_applied_to_mcx(market):
    with pytest.raises(ValueError):
        capture(market, institutional_flows=(flow(),))


@pytest.mark.parametrize(
    "changes",
    [
        dict(market="BANKNIFTY"),
        dict(as_of=NOW.replace(tzinfo=None)),
        dict(global_observations=[global_obs()]),
        dict(global_observations=(global_obs(), global_obs())),
        dict(institutional_flows=(flow(), flow())),
        dict(scheduled_events=(event(), event())),
        dict(scheduled_events=(event(affected_markets=("SENSEX",)),)),
        dict(point_in_time_verified=True, historical_retrieval=True),
        dict(point_in_time_verified=True, capture_verified=False),
        dict(capture_verified=1),
        dict(point_in_time_verified=1),
        dict(historical_retrieval=1),
    ],
)
def test_invalid_capture_boundary(changes):
    with pytest.raises(ValueError):
        capture(**changes)


def test_future_availability_cannot_enter_point_in_time_capture():
    with pytest.raises(ValueError):
        capture(global_observations=(global_obs(available_at=NOW + timedelta(minutes=1)),))


def test_historical_retrieval_is_explicit_not_live():
    c = capture(point_in_time_verified=False, historical_retrieval=True)
    r = validate(c)
    assert r.status == "PARTIAL"
    assert "POINT_IN_TIME_AVAILABILITY_UNPROVEN" in r.warnings


def test_empty_capture_fails_closed():
    c = capture(global_observations=(), institutional_flows=(), scheduled_events=())
    r = validate(c)
    assert r.status == "UNAVAILABLE"
    assert "NO_VERIFIED_CONTEXT_FAMILY" in r.blockers


def test_unverified_capture_fails_closed_even_with_record_values():
    c = capture(capture_verified=False, point_in_time_verified=False)
    r = validate(c)
    assert r.status == "UNAVAILABLE"
    assert "CAPTURE_UNVERIFIED" in r.blockers


def test_outdated_global_record_does_not_become_zero():
    c = capture(global_observations=(global_obs(),), institutional_flows=(), scheduled_events=())
    result = validate(c, global_max_age_seconds=10)
    assert result.global_status == "UNAVAILABLE"
    assert result.status == "UNAVAILABLE"


def test_available_at_later_than_capture_is_not_usable_in_retrospective_replay():
    c = capture(
        point_in_time_verified=False,
        historical_retrieval=True,
        global_observations=(global_obs(available_at=NOW + timedelta(minutes=1)),),
        institutional_flows=(),
        scheduled_events=(),
    )
    assert validate(c).global_status == "UNAVAILABLE"


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), "300"])
def test_freshness_budgets_reject_invalid_values(bad):
    with pytest.raises(ValueError):
        validate(capture(), global_max_age_seconds=bad)


def test_type_rejections_for_validation():
    with pytest.raises(TypeError):
        validate_x7_context_v1(
            None,
            global_max_age_seconds=10,
            institutional_max_age_seconds=10,
            event_max_age_seconds=10,
        )


def test_no_new_data_is_created_when_a_family_is_missing():
    c = capture(global_observations=(), scheduled_events=())
    r = validate(c)
    assert r.global_status == "UNAVAILABLE"
    assert r.event_status == "UNAVAILABLE"
    assert r.institutional_status == "AVAILABLE"
    assert r.status == "PARTIAL"


def test_immutable_contracts_and_semantic_sha():
    c = capture()
    with pytest.raises(FrozenInstanceError):
        c.market = "GOLDM"
    with pytest.raises(FrozenInstanceError):
        c.global_observations[0].value = 20
    result = validate(c)
    with pytest.raises(FrozenInstanceError):
        result.status = "AVAILABLE"
    assert c.sha256() == capture().sha256()
    assert c.sha256() != replace(c, capture_id="CAPTURE:2").sha256()
    assert result.sha256() == validate(c).sha256()
    assert len(c.sha256()) == 64
    assert c.to_dict()["as_of"] == NOW.isoformat()


@pytest.mark.parametrize(
    "field",
    [
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ],
)
def test_no_authority_can_be_acquired(field):
    for obj in (global_obs(), flow(), event(), capture(), validate(capture())):
        with pytest.raises(ValueError):
            replace(obj, **{field: True})


@pytest.mark.parametrize("obj", [global_obs(), flow(), event(), capture(), validate(capture())])
def test_schema_and_data_only_flags_are_immutable(obj):
    with pytest.raises(ValueError):
        replace(obj, schema_version="OTHER")
    with pytest.raises(ValueError):
        replace(obj, data_only=False)


def test_static_source_audit_disallows_broker_apis():
    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "services/x7").glob("*.py"))
    required = {"__init__.py", "contracts_v1.py", "input_validation_v1.py"}
    assert required.issubset({p.name for p in files})
    blocked_imports = (
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
    blocked_calls = {
        "place_order",
        "placeOrder",
        "submit_order",
        "send_order",
        "execute_trade",
        "modifyOrder",
        "cancelOrder",
    }
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                names = []
            assert not any(
                name == item or name.startswith(item + ".")
                for name in names
                for item in blocked_imports
            ), (path, names)
            if isinstance(node, ast.Call):
                method = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else (node.func.id if isinstance(node.func, ast.Name) else "")
                )
                assert method not in blocked_calls, (path, method)

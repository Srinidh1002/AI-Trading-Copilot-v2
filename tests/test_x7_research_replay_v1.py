"""B4: five-market exact-source research views, dependency control and replay."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from services.x7.contracts_v1 import GLOBAL_TYPES, GLOBAL_UNITS, MARKETS, canonical_sha256
from services.x7.event_adapter_v1 import (
    X7EventSourceProofV1,
    adapt_x7_scheduled_event_batch_v1,
)
from services.x7.global_adapter_v1 import (
    X7GlobalSourceProofV1,
    adapt_x7_global_batch_v1,
)
from services.x7.institutional_adapter_v1 import (
    X7InstitutionalSourceProofV1,
    adapt_x7_institutional_batch_v1,
)
from services.x7.replay_provenance_v1 import (
    X7ReplayCheckV1,
    X7ReplayTimelineV1,
    audit_x7_replay_timeline_v1,
    replay_x7_research_view_v1,
)
from services.x7.research_view_v1 import (
    X7ResearchViewV1,
    X7SourceTraceV1,
    build_x7_research_view_v1,
)

NOW = datetime(2026, 10, 2, 10, 30, tzinfo=UTC)
T0 = NOW - timedelta(seconds=90)
PUB = NOW - timedelta(seconds=75)
AVAIL = NOW - timedelta(seconds=60)
EVENT = NOW + timedelta(days=1)
SESSION = "X7_SESSION_20261002"
CAPTURE = "X7_CAPTURE_B4"


def g_proof(name="SP500", **changes):
    values = dict(
        name=name,
        observation_type=GLOBAL_TYPES[name],
        unit=GLOBAL_UNITS[name],
        session_reference="PREVIOUS_CLOSE"
        if GLOBAL_TYPES[name] == "INDEX_CLOSE"
        else "CURRENT_SESSION",
        source_id="GLOBAL_SOURCE",
        source_record_id=f"G:{name}:1",
        observed_at=T0,
        published_at=PUB,
        available_at=AVAIL,
        source_verified=True,
        timestamp_semantics_verified=True,
        value_unit_verified=True,
        value_verified=True,
    )
    values.update(changes)
    return X7GlobalSourceProofV1(**values)


def g_raw(p, **changes):
    keys = (
        "name",
        "observation_type",
        "unit",
        "session_reference",
        "source_id",
        "source_record_id",
        "observed_at",
        "published_at",
        "available_at",
    )
    result = {key: getattr(p, key) for key in keys}
    result.update(value=100.0, previous_value=99.0)
    result.update(changes)
    return result


def i_proof(**changes):
    values = dict(
        trading_date=date(2026, 10, 2),
        applicable_markets=("NIFTY", "SENSEX"),
        flow_unit="CRORE_INR",
        source_id="INSTITUTION_SOURCE",
        source_record_id="I:20261002",
        observed_at=T0,
        published_at=PUB,
        available_at=AVAIL,
        publication_state="FINAL",
        source_verified=True,
        timestamp_semantics_verified=True,
        value_unit_verified=True,
        values_verified=True,
    )
    values.update(changes)
    return X7InstitutionalSourceProofV1(**values)


def i_raw(p, **changes):
    keys = (
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
    result = {key: getattr(p, key) for key in keys}
    result.update(fii_net=-10.0, dii_net=20.0)
    result.update(changes)
    return result


def e_proof(**changes):
    values = dict(
        event_id="RBI:20261003",
        category="RBI_POLICY",
        scheduled_at=EVENT,
        affected_markets=MARKETS,
        severity="HIGH",
        source_id="CALENDAR_SOURCE",
        source_record_id="E:RBI:20261003",
        observed_at=T0,
        published_at=PUB,
        available_at=AVAIL,
        schedule_state="CONFIRMED",
        bound_contract_id=None,
        bound_contract_expiry=None,
        source_verified=True,
        timestamp_semantics_verified=True,
        schedule_verified=True,
        calendar_reference_verified=False,
        contract_binding_verified=False,
    )
    values.update(changes)
    return X7EventSourceProofV1(**values)


def e_raw(p, **changes):
    keys = (
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
    result = {key: getattr(p, key) for key in keys}
    result.update(changes)
    return result


def fixture(
    *,
    market="NIFTY",
    names=("SP500", "NASDAQ", "INDIA_VIX"),
    institutional=True,
    events=True,
    as_of=NOW,
    session_id=SESSION,
    capture_id=CAPTURE,
    pit=True,
    historical=False,
    source_verified=True,
    event_proof=None,
):
    gps = tuple(
        g_proof(name, source_verified=source_verified, value_verified=source_verified)
        for name in names
    )
    grs = tuple(g_raw(p) for p in gps)
    global_budget = {p.name: 600.0 for p in gps}
    common = dict(market=market, session_id=session_id, capture_id=capture_id, as_of=as_of)
    gb = adapt_x7_global_batch_v1(
        **common,
        raw_records=grs,
        proofs=gps,
        max_age_seconds_by_name=global_budget,
    )
    if institutional and market in ("NIFTY", "SENSEX"):
        ips = (i_proof(source_verified=source_verified, values_verified=source_verified),)
        irs = tuple(i_raw(p) for p in ips)
        ib = adapt_x7_institutional_batch_v1(
            **common,
            raw_records=irs,
            proofs=ips,
            max_age_seconds=600.0,
        )
    else:
        ips, irs, ib = (), (), None
    if events:
        eps = (
            event_proof
            or e_proof(source_verified=source_verified, schedule_verified=source_verified),
        )
        ers = tuple(e_raw(p) for p in eps)
        eb = adapt_x7_scheduled_event_batch_v1(
            **common,
            raw_records=ers,
            proofs=eps,
            max_age_seconds=600.0,
        )
    else:
        eps, ers, eb = (), (), None
    view = build_x7_research_view_v1(
        global_batch=gb,
        institutional_batch=ib,
        event_batch=eb,
        capture_verified=True,
        point_in_time_verified=pit,
        historical_retrieval=historical,
        global_max_age_seconds=600.0,
        institutional_max_age_seconds=600.0,
        event_max_age_seconds=600.0,
    )
    replay = dict(
        view=view,
        expected_view_sha256=view.sha256(),
        global_raw_records=grs,
        global_proofs=gps,
        global_max_age_seconds_by_name=global_budget,
        institutional_raw_records=irs,
        institutional_proofs=ips,
        event_raw_records=ers,
        event_proofs=eps,
    )
    return view, replay, (gb, ib, eb)


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize(
    "names", ((), ("SP500",), ("SP500", "NASDAQ"), ("SP500", "NASDAQ", "INDIA_VIX"))
)
def test_five_market_available_partial_and_empty_source_views(market, names):
    view, original, _ = fixture(market=market, names=names)
    assert view.capture.market == market
    assert view.validation.source_capture_sha256 == view.capture.sha256()
    assert view.status == (
        "AVAILABLE"
        if market in ("NIFTY", "SENSEX") and names
        else "PARTIAL"
        if names or view.capture.scheduled_events
        else "UNAVAILABLE"
    )
    assert view.data_only and not view.independent_vote
    assert not view.live_execution_eligible
    assert replay_x7_research_view_v1(**original).status == "MATCH"


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("name", GLOBAL_TYPES)
def test_each_global_name_has_single_exact_source_trace(market, name):
    view, replay, _ = fixture(market=market, names=(name,))
    trace = next(x for x in view.source_traces if x.family == "GLOBAL")
    assert trace.fact_id == name
    assert trace.status == "AVAILABLE"
    assert trace.raw_record_sha256 == canonical_sha256(dict(replay["global_raw_records"][0]))
    assert trace.proof_sha256 == replay["global_proofs"][0].sha256()
    assert replay_x7_research_view_v1(**replay).original_view_sha256 == view.sha256()


def test_fixed_global_correlated_groups_and_source_reuse_are_descriptive():
    view, _, _ = fixture(names=("SP500", "NASDAQ", "DOW_JONES", "INDIA_VIX"))
    groups = dict(view.dependency_groups)
    assert groups["GLOBAL:US_EQUITY_CLOSES"] == (
        "GLOBAL:SP500",
        "GLOBAL:NASDAQ",
        "GLOBAL:DOW_JONES",
    )
    assert groups["GLOBAL:INDIA_VOLATILITY"] == ("GLOBAL:INDIA_VIX",)
    assert groups["INSTITUTIONAL:CASH_EQUITY"] == ("INSTITUTIONAL:2026-10-02",)
    assert groups["EVENT:RBI_POLICY"] == ("EVENT:RBI:20261003",)
    assert dict(view.shared_source_groups)["GLOBAL_SOURCE"] == (
        "GLOBAL:DOW_JONES",
        "GLOBAL:INDIA_VIX",
        "GLOBAL:NASDAQ",
        "GLOBAL:SP500",
    )
    assert "votes" not in asdict(view)
    assert "score" not in asdict(view)


@pytest.mark.parametrize("status", ("FINAL", "PROVISIONAL", "UNAVAILABLE"))
def test_institutional_publication_fidelity(status):
    if status == "FINAL":
        view, replay, _ = fixture()
    else:
        # Source stays attested but the flow is never promoted to verified FINAL.
        p = i_proof(publication_state=status, values_verified=status != "UNAVAILABLE")
        record = i_raw(p, fii_net=None, dii_net=None) if status == "UNAVAILABLE" else i_raw(p)
        view, replay, (gb, _, eb) = fixture()
        ib = adapt_x7_institutional_batch_v1(
            market="NIFTY",
            session_id=SESSION,
            capture_id=CAPTURE,
            as_of=NOW,
            raw_records=(record,),
            proofs=(p,),
            max_age_seconds=600.0,
        )
        view = build_x7_research_view_v1(
            global_batch=gb,
            institutional_batch=ib,
            event_batch=eb,
            capture_verified=True,
            point_in_time_verified=True,
            historical_retrieval=False,
            global_max_age_seconds=600.0,
            institutional_max_age_seconds=600.0,
            event_max_age_seconds=600.0,
        )
        replay.update(
            view=view,
            expected_view_sha256=view.sha256(),
            institutional_raw_records=(record,),
            institutional_proofs=(p,),
        )
        assert view.status == "PARTIAL"
        assert view.validation.institutional_status == "UNAVAILABLE"
    assert replay_x7_research_view_v1(**replay).status == "MATCH"


@pytest.mark.parametrize("market", ("CRUDEOILM", "GOLDM", "NATGASMINI"))
def test_mcx_cannot_inherit_equity_cash_flow(market):
    view, replay, batches = fixture(market=market)
    assert batches[1] is None and view.institutional_batch_sha256 is None
    assert view.validation.institutional_status == "UNAVAILABLE"
    assert replay_x7_research_view_v1(**replay).status == "MATCH"
    index_ib = fixture()[2][1]
    with pytest.raises(ValueError):
        build_x7_research_view_v1(
            global_batch=batches[0],
            institutional_batch=index_ib,
            event_batch=batches[2],
            capture_verified=True,
            point_in_time_verified=True,
            historical_retrieval=False,
            global_max_age_seconds=600,
            institutional_max_age_seconds=600,
            event_max_age_seconds=600,
        )


@pytest.mark.parametrize("market", MARKETS)
def test_absent_event_family_does_not_get_implicit_calendar_evidence(market):
    view, replay, _ = fixture(market=market, events=False)
    assert view.event_batch_sha256 is None
    assert view.validation.event_status == "UNAVAILABLE"
    assert view.status == "PARTIAL"
    assert replay_x7_research_view_v1(**replay).status == "MATCH"


@pytest.mark.parametrize("market", MARKETS)
def test_retrospective_replay_cannot_promote_point_in_time(market):
    view, replay, _ = fixture(market=market, pit=False, historical=True)
    assert view.status == "PARTIAL"
    assert view.capture.historical_retrieval and not view.capture.point_in_time_verified
    assert "POINT_IN_TIME_AVAILABILITY_UNPROVEN" in view.validation.warnings
    assert replay_x7_research_view_v1(**replay).status == "MATCH"


@pytest.mark.parametrize("field", ("value", "previous_value", "name", "source_record_id"))
def test_tampered_global_raw_record_never_replays(field):
    view, args, _ = fixture()
    rec = dict(args["global_raw_records"][0])
    rec[field] = {
        "value": 101.0,
        "previous_value": 97.0,
        "name": "DXY",
        "source_record_id": "FAKE",
    }[field]
    args["global_raw_records"] = (rec,) + args["global_raw_records"][1:]
    with pytest.raises(ValueError):
        replay_x7_research_view_v1(**args)
    assert view.sha256() == args["expected_view_sha256"]


@pytest.mark.parametrize("field", ("fii_net", "dii_net", "source_id", "published_at"))
def test_tampered_institutional_raw_record_never_replays(field):
    _, args, _ = fixture()
    rec = dict(args["institutional_raw_records"][0])
    rec[field] = {
        "fii_net": -12.0,
        "dii_net": 30.0,
        "source_id": "MALICIOUS",
        "published_at": PUB + timedelta(seconds=1),
    }[field]
    args["institutional_raw_records"] = (rec,)
    with pytest.raises(ValueError):
        replay_x7_research_view_v1(**args)


@pytest.mark.parametrize("field", ("severity", "schedule_state", "event_id", "scheduled_at"))
def test_tampered_event_raw_record_never_replays(field):
    _, args, _ = fixture()
    rec = dict(args["event_raw_records"][0])
    rec[field] = {
        "severity": "LOW",
        "schedule_state": "POSTPONED",
        "event_id": "CHANGED",
        "scheduled_at": EVENT + timedelta(days=1),
    }[field]
    args["event_raw_records"] = (rec,)
    with pytest.raises(ValueError):
        replay_x7_research_view_v1(**args)


@pytest.mark.parametrize("family", ("global", "institutional", "event"))
def test_tampered_proof_never_replays(family):
    _, args, _ = fixture()
    key = f"{family}_proofs"
    old = args[key][0]
    args[key] = (replace(old, source_record_id=old.source_record_id + ":CHANGED"),) + args[key][1:]
    with pytest.raises(ValueError):
        replay_x7_research_view_v1(**args)


@pytest.mark.parametrize(
    "field",
    (
        "global_batch_sha256",
        "institutional_batch_sha256",
        "event_batch_sha256",
        "global_max_age_seconds",
        "institutional_max_age_seconds",
        "event_max_age_seconds",
        "provenance_sha256",
        "status",
        "dependency_groups",
        "shared_source_groups",
    ),
)
def test_forged_or_modified_persisted_view_fails_external_anchor(field):
    view, args, _ = fixture()
    forged = object.__new__(X7ResearchViewV1)
    for name in view.__dataclass_fields__:
        object.__setattr__(forged, name, getattr(view, name))
    value = (
        601
        if field.endswith("age_seconds")
        else "UNAVAILABLE"
        if field == "status"
        else (
            (("GLOBAL:FAKE", ("GLOBAL:FAKE",)),)
            if field == "dependency_groups"
            else (("FAKE", ("GLOBAL:FAKE",)),)
            if field == "shared_source_groups"
            else "0" * 64
        )
    )
    object.__setattr__(forged, field, value)
    args["view"] = forged
    with pytest.raises(ValueError, match="checksum"):
        replay_x7_research_view_v1(**args)


@pytest.mark.parametrize(
    "field,invalid",
    (
        ("global_max_age_seconds", 0),
        ("institutional_max_age_seconds", float("nan")),
        ("event_max_age_seconds", True),
        ("capture_verified", 1),
        ("point_in_time_verified", "yes"),
        ("historical_retrieval", None),
    ),
)
def test_invalid_composition_settings_rejected(field, invalid):
    _, _, (gb, ib, eb) = fixture()
    params = dict(
        global_batch=gb,
        institutional_batch=ib,
        event_batch=eb,
        capture_verified=True,
        point_in_time_verified=True,
        historical_retrieval=False,
        global_max_age_seconds=600,
        institutional_max_age_seconds=600,
        event_max_age_seconds=600,
    )
    params[field] = invalid
    with pytest.raises(ValueError):
        build_x7_research_view_v1(**params)


@pytest.mark.parametrize("batch", ("institutional_batch", "event_batch"))
@pytest.mark.parametrize("key", ("market", "session_id", "capture_id", "as_of"))
def test_mismatched_batch_identity_rejected(batch, key):
    _, _, (gb, ib, eb) = fixture()
    obj = {"institutional_batch": ib, "event_batch": eb}[batch]
    value = (
        "SENSEX"
        if key == "market"
        else "OTHER"
        if key in {"session_id", "capture_id"}
        else NOW + timedelta(seconds=1)
    )
    params = dict(
        global_batch=gb,
        institutional_batch=ib,
        event_batch=eb,
        capture_verified=True,
        point_in_time_verified=True,
        historical_retrieval=False,
        global_max_age_seconds=600,
        institutional_max_age_seconds=600,
        event_max_age_seconds=600,
    )
    with pytest.raises(ValueError):
        params[batch] = replace(obj, **{key: value})
        build_x7_research_view_v1(**params)


def test_cross_family_reused_publisher_record_rejected():
    _, _, (gb, ib, _) = fixture()
    gp = g_proof()
    ep = e_proof(source_id=gp.source_id, source_record_id=gp.source_record_id)
    eb = adapt_x7_scheduled_event_batch_v1(
        market="NIFTY",
        session_id=SESSION,
        capture_id=CAPTURE,
        as_of=NOW,
        raw_records=(e_raw(ep),),
        proofs=(ep,),
        max_age_seconds=600,
    )
    with pytest.raises(ValueError, match="reused"):
        build_x7_research_view_v1(
            global_batch=gb,
            institutional_batch=ib,
            event_batch=eb,
            capture_verified=True,
            point_in_time_verified=True,
            historical_retrieval=False,
            global_max_age_seconds=600,
            institutional_max_age_seconds=600,
            event_max_age_seconds=600,
        )


def test_timeline_replay_sorted_by_market_and_time():
    a, _, _ = fixture()
    b, _, _ = fixture(market="SENSEX", capture_id="SENSEX:1")
    c, _, _ = fixture(as_of=NOW + timedelta(seconds=30), capture_id="NIFTY:2", pit=False)
    views = (a, b, c)
    hashes = tuple(view.sha256() for view in views)
    timeline = audit_x7_replay_timeline_v1(views=views, expected_view_hashes=hashes)
    assert timeline.view_hashes == hashes
    assert timeline.retrospective_view_hashes == (c.sha256(),)
    assert len(timeline.sha256()) == 64


@pytest.mark.parametrize("case", ("duplicate", "backwards", "same_instant", "wrong_anchor"))
def test_timeline_ambiguous_history_rejected(case):
    a, _, _ = fixture()
    if case == "duplicate":
        b = a
    elif case == "backwards":
        b = fixture(as_of=NOW - timedelta(seconds=1), capture_id="CAPTURE:PREV")[0]
    elif case == "same_instant":
        b = fixture(capture_id="CAPTURE:OTHER")[0]
    else:
        b = fixture(as_of=NOW + timedelta(seconds=10), capture_id="CAPTURE:NEXT")[0]
    hashes = (a.sha256(), b.sha256())
    if case == "wrong_anchor":
        hashes = (a.sha256(), "0" * 64)
    with pytest.raises(ValueError):
        audit_x7_replay_timeline_v1(views=(a, b), expected_view_hashes=hashes)


@pytest.mark.parametrize(
    "klass", (X7ResearchViewV1, X7SourceTraceV1, X7ReplayCheckV1, X7ReplayTimelineV1)
)
def test_all_b4_outputs_have_immutable_zero_authority(klass):
    view, args, _ = fixture()
    result = (
        view
        if klass is X7ResearchViewV1
        else view.source_traces[0]
        if klass is X7SourceTraceV1
        else replay_x7_research_view_v1(**args)
        if klass is X7ReplayCheckV1
        else audit_x7_replay_timeline_v1(views=(view,), expected_view_hashes=(view.sha256(),))
    )
    assert result.schema_version.startswith("X7_")
    assert result.data_only and result.independent_vote is False
    for field in (
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ):
        assert getattr(result, field) is False
    with pytest.raises(FrozenInstanceError):
        result.live_execution_eligible = True


def test_new_x7_sources_have_no_broker_network_decision_calls():
    blocked = (
        "fyers_apiv3",
        "SmartApi",
        "services.execution",
        "services.broker",
        "services.paper_orchestration",
        "services.paper_trading",
        "services.trading",
        "services.risk",
        "subprocess",
        "socket",
        "requests",
        "httpx",
    )
    blocked_calls = {
        "place_order",
        "placeOrder",
        "submit_order",
        "send_order",
        "cancel_order",
        "execute_trade",
        "modify_order",
    }
    files = sorted(Path("services/x7").glob("*.py"))
    assert len(files) == 8
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not any(x.name == b or x.name.startswith(b + ".") for b in blocked)
                    for x in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                assert not any(
                    (node.module or "") == b or (node.module or "").startswith(b + ".")
                    for b in blocked
                )
            elif isinstance(node, ast.Call):
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else (node.func.id if isinstance(node.func, ast.Name) else "")
                )
                assert name not in blocked_calls

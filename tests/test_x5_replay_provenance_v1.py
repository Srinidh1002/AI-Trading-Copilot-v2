"""Offline adversarial X5-B4 replay, hash consistency and research-only safety."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from test_x5_chain_contracts_v1 import MARKETS, NOW, capture, observation

from services.x5.analytics_v1 import analyze_x5_chain_v1
from services.x5.chain_validation_v1 import METRICS, validate_x5_chain_v1
from services.x5.contracts_v1 import canonical_sha256
from services.x5.replay_provenance_v1 import (
    X5ReplayFrameV1,
    X5ReplayRecordV1,
    X5ReplayResultV1,
    replay_x5_history_v1,
    seal_x5_replay_frame_v1,
)
from services.x5.research_view_v1 import build_x5_research_view_v1


def frame(c=None):
    return seal_x5_replay_frame_v1(capture=c if c is not None else capture(), max_age_seconds=60)


def replay(*frames, age=60, gap=60):
    return replay_x5_history_v1(frames=tuple(frames), max_age_seconds=age, max_step_seconds=gap)


def next_capture(c=None, *, seconds=20, **changes):
    c = c if c is not None else capture()
    updates = dict(
        as_of=c.as_of + timedelta(seconds=seconds),
        captured_at=c.as_of + timedelta(seconds=seconds),
        capture_id=c.capture_id + f":{seconds}",
        source_id=c.source_id + f":{seconds}",
    )
    updates.update(changes)
    return replace(c, **updates)


@pytest.mark.parametrize("market", tuple(MARKETS))
def test_each_market_single_frame_replay_has_exact_identity(market):
    c = capture(market)
    r = replay(frame(c))
    assert r.market == market
    assert r.expiry == c.contract.expiry
    assert r.session_id == c.session_id
    assert r.records[0].capture_id == c.capture_id
    assert r.records[0].available_metrics == METRICS
    assert r.records[0].scope == "CAPTURED_STRIKE_WINDOW"


@pytest.mark.parametrize("market", tuple(MARKETS))
def test_all_markets_two_checkpoint_stable_window(market):
    c = capture(market)
    result = replay(frame(c), frame(next_capture(c)))
    assert result.source_frame_count == 2
    assert tuple(x.coverage_transition for x in result.records) == ("FIRST_FRAME", "SAME_WINDOW")
    assert result.records[1].previous_record_sha256 == result.records[0].sha256()
    assert result.window_transition_count == 0
    assert result.retrospective_count == 0


@pytest.mark.parametrize("metric", METRICS)
def test_each_metric_preserved_in_valid_contemporaneous_replay(metric):
    source = frame()
    result = replay(source)
    assert metric in result.records[0].available_metrics
    assert next(x for x in source.view.features if x.metric_name == metric).status == "AVAILABLE"
    assert result.records[0].observation_provenance == "CONTEMPORANEOUS_ATTESTED"


@pytest.mark.parametrize("metric", METRICS)
def test_each_metric_unavailable_for_retrospective_replay(metric):
    c = capture(
        historical_retrieval=True, point_in_time_verified=False, captured_at=NOW + timedelta(days=1)
    )
    sealed = frame(c)
    result = replay(sealed)
    assert metric not in result.records[0].available_metrics
    assert result.records[0].observation_provenance == "RETROSPECTIVE_UNPROVEN"
    assert result.records[0].research_status == "UNAVAILABLE"
    assert result.retrospective_count == 1
    assert "POINT_IN_TIME_AVAILABILITY_UNPROVEN" in result.records[0].warnings


@pytest.mark.parametrize("market", tuple(MARKETS))
def test_retrospective_unproven_for_all_markets(market):
    c = capture(
        market,
        historical_retrieval=True,
        point_in_time_verified=False,
        captured_at=NOW + timedelta(hours=2),
    )
    result = replay(frame(c))
    assert result.records[0].available_metrics == ()
    assert result.records[0].observation_provenance == "RETROSPECTIVE_UNPROVEN"


@pytest.mark.parametrize("metric", METRICS)
def test_no_data_capture_never_creates_metric(metric):
    c = capture(capture_verified=False, point_in_time_verified=False)
    result = replay(frame(c))
    assert metric not in result.records[0].available_metrics
    assert result.records[0].research_status == "UNAVAILABLE"


def test_unverified_contemporaneous_capture_is_distinct_from_retrospective():
    c = capture(point_in_time_verified=False)
    result = replay(frame(c))
    assert result.records[0].observation_provenance == "POINT_IN_TIME_UNPROVEN"
    assert result.records[0].available_metrics == ()
    assert result.retrospective_count == 0


def test_window_change_marked_not_silently_compared():
    c = capture()
    added = (
        observation("NIFTY", "CE", 110.0, serial="2"),
        observation("NIFTY", "PE", 110.0, serial="2"),
    )
    second = next_capture(c, observations=c.observations + added)
    result = replay(frame(c), frame(second))
    assert result.records[1].coverage_transition == "WINDOW_CHANGED"
    assert "NON_COMPARABLE_STRIKE_WINDOW" in result.records[1].warnings
    assert result.window_transition_count == 1
    assert result.records[0].captured_window_sha256 != result.records[1].captured_window_sha256
    assert result.cross_frame_metric_comparison_allowed is False


def test_window_change_even_if_both_have_complete_pairs():
    c = capture()
    replacement = (
        observation("NIFTY", "CE", 110.0, serial="2"),
        observation("NIFTY", "PE", 110.0, serial="2"),
    )
    second = next_capture(c, observations=replacement)
    result = replay(frame(c), frame(second))
    assert result.records[1].coverage_transition == "WINDOW_CHANGED"
    assert "OI_SUPPORT_RESISTANCE" not in result.records[1].available_metrics
    assert result.records[1].available_metrics
    assert result.cross_frame_metric_comparison_allowed is False


def test_incomplete_pair_and_unverified_oi_do_not_gain_values_in_replay():
    c = capture(observations=(observation("NIFTY", "CE"),))
    result = replay(frame(c))
    assert result.records[0].available_metrics == ()
    assert result.records[0].research_status == "UNAVAILABLE"


def test_cross_expiry_rollover_rejected_and_must_use_separate_replay():
    c = capture()
    later_expiry = date(2026, 11, 26)
    rows = tuple(
        replace(
            x,
            expiry=later_expiry,
            canonical_option_id=x.canonical_option_id + ":NEW",
            source_record_id=x.source_record_id + ":NEW",
            provider_symbol=x.provider_symbol.replace("26OCT", "26NOV"),
        )
        for x in c.observations
    )
    second = next_capture(
        c,
        contract=replace(c.contract, expiry=later_expiry, expiry_source_id="NEW_PROVIDER_EXPIRY"),
        observations=rows,
    )
    with pytest.raises(ValueError, match="expiry|contract"):
        replay(frame(c), frame(second))
    assert replay(frame(second)).expiry == later_expiry


@pytest.mark.parametrize("market", tuple(m for m in MARKETS if m != "NIFTY"))
def test_cross_market_replay_rejected(market):
    c = capture()
    other = next_capture(capture(market))
    with pytest.raises(ValueError, match="market|contract"):
        replay(frame(c), frame(other))


def test_other_underlying_symbol_same_market_rejected():
    c = capture("CRUDEOILM")
    other = next_capture(
        c, contract=replace(c.contract, underlying_provider_symbol="MCX:CRUDEOILMOTHER")
    )
    with pytest.raises(ValueError, match="contract"):
        replay(frame(c), frame(other))


def test_cross_session_identifier_rejected():
    c = capture()
    other = next_capture(c, session_id="SECOND_SESSION")
    with pytest.raises(ValueError, match="session"):
        replay(frame(c), frame(other))


def test_cross_local_session_day_rejected_even_if_session_id_reused():
    c = capture()
    next_day = next_capture(
        c,
        seconds=86400,
        observations=tuple(
            replace(
                x,
                observed_at=x.observed_at + timedelta(days=1),
                source_record_id=x.source_record_id + ":NEXTDAY",
            )
            for x in c.observations
        ),
    )
    with pytest.raises(ValueError, match="checkpoint|session"):
        replay(frame(c), frame(next_day), gap=90000)


@pytest.mark.parametrize("seconds", [0, -1, -20])
def test_duplicate_or_reverse_checkpoint_rejected(seconds):
    c = capture()
    second = next_capture(
        c,
        seconds=seconds,
        observations=tuple(
            replace(
                x,
                observed_at=x.observed_at + timedelta(seconds=min(seconds, 0)),
                source_record_id=x.source_record_id + f":BACK:{seconds}",
            )
            for x in c.observations
        ),
    )
    with pytest.raises(ValueError, match="checkpoint"):
        replay(frame(c), frame(second))


def test_gap_rejected_even_when_individual_snapshots_are_valid():
    c = capture()
    later = next_capture(
        c,
        seconds=120,
        observations=tuple(
            replace(
                x,
                observed_at=x.observed_at + timedelta(seconds=110),
                source_record_id=x.source_record_id + ":LATER",
            )
            for x in c.observations
        ),
    )
    with pytest.raises(ValueError, match="gap budget"):
        replay(frame(c), frame(later), gap=60)
    assert replay(frame(c), frame(later), gap=120).source_frame_count == 2


def test_duplicate_capture_id_rejected_even_when_times_differ():
    c = capture()
    second = next_capture(c, capture_id=c.capture_id)
    with pytest.raises(ValueError, match="Duplicate capture"):
        replay(frame(c), frame(second))


def test_duplicate_capture_source_id_rejected_even_when_capture_id_differs():
    c = capture()
    second = next_capture(c, source_id=c.source_id)
    with pytest.raises(ValueError, match="source identity"):
        replay(frame(c), frame(second))


def test_source_record_identity_cannot_change_under_same_id():
    c = capture()
    changed = tuple(replace(x, ltp=x.ltp + 1) for x in c.observations)
    second = next_capture(c, observations=changed)
    with pytest.raises(ValueError, match="conflicting content"):
        replay(frame(c), frame(second))


def test_same_strike_contract_identity_cannot_change_between_captures():
    c = capture()
    rows = tuple(
        replace(
            x,
            canonical_option_id=x.canonical_option_id + ":OTHER",
            source_record_id=x.source_record_id + ":OTHER",
        )
        for x in c.observations
    )
    changed = next_capture(c, observations=rows)
    with pytest.raises(ValueError, match="Canonical option contract changed"):
        replay(frame(c), frame(changed))


def test_source_record_identity_may_repeat_with_identical_content():
    c = capture()
    second = next_capture(c)
    assert replay(frame(c), frame(second)).records[1].coverage_transition == "SAME_WINDOW"


@pytest.mark.parametrize(
    "field",
    [
        "expected_capture_sha256",
        "expected_validation_sha256",
        "expected_analytics_sha256",
        "expected_view_sha256",
    ],
)
def test_witness_mutation_detected(field):
    sealed = frame()
    changed = replace(sealed, **{field: "f" * 64})
    with pytest.raises(ValueError, match="witness hash"):
        replay(changed)


@pytest.mark.parametrize(
    "field",
    [
        "expected_capture_sha256",
        "expected_validation_sha256",
        "expected_analytics_sha256",
        "expected_view_sha256",
    ],
)
def test_malformed_witness_hash_rejected(field):
    with pytest.raises(ValueError, match="SHA-256"):
        replace(frame(), **{field: "not-a-hash"})


def test_wrong_row_witness_detected():
    sealed = frame()
    rows = list(sealed.expected_row_seals)
    rows[0] = (rows[0][0], "a" * 64)
    with pytest.raises(ValueError, match="Per-row witness"):
        replay(replace(sealed, expected_row_seals=tuple(rows)))


def test_replay_row_witness_catches_modified_capture():
    sealed = frame()
    source = sealed.capture
    changed = replace(
        source, observations=tuple(replace(x, volume=x.volume + 1) for x in source.observations)
    )
    mutated = replace(sealed, capture=changed)
    with pytest.raises(ValueError, match="witness hash"):
        replay(mutated)


def test_malicious_resealing_does_not_claim_provider_authenticity():
    source = capture()
    changed = replace(source, underlying_value=source.underlying_value + 1)
    other = frame(changed)
    assert other.expected_capture_sha256 != frame(source).expected_capture_sha256
    # Locally consistent hashes are not proof of an independently verified provider.
    assert other.capture.capture_verified is True
    assert other.data_only is True


@pytest.mark.parametrize("which", ["validation", "analytics", "view"])
def test_tampered_downstream_object_cannot_be_replayed(which):
    sealed = frame()
    source = getattr(sealed, which)
    mutated = replace(source, warnings=source.warnings + ("FORGED_WARNING",))
    with pytest.raises(ValueError, match="witness hash"):
        replay(replace(sealed, **{which: mutated}))


@pytest.mark.parametrize("which", ["validation", "analytics", "view"])
def test_downstream_reseal_still_fails_recomputation(which):
    sealed = frame()
    source = getattr(sealed, which)
    mutated = replace(source, warnings=source.warnings + ("FORGED_WARNING",))
    args = {
        which: mutated,
        f"expected_{which if which != 'view' else 'view'}_sha256": mutated.sha256(),
    }
    with pytest.raises(ValueError, match="disagrees"):
        replay(replace(sealed, **args))


def test_revalidated_freshness_policy_mismatch_detected():
    sealed = frame()
    with pytest.raises(ValueError, match="disagrees"):
        replay(sealed, age=5)


def test_replayed_validation_analytics_and_view_recompute_exactly():
    sealed = frame()
    c = sealed.capture
    validation = validate_x5_chain_v1(c, max_age_seconds=60)
    analytics = analyze_x5_chain_v1(capture=c, max_age_seconds=60)
    view = build_x5_research_view_v1(capture=c, validation=validation, analytics=analytics)
    assert sealed.validation == validation and sealed.analytics == analytics and sealed.view == view
    result = replay(sealed)
    assert result.records[0].source_validation_sha256 == validation.sha256()
    assert result.records[0].source_analytics_sha256 == analytics.sha256()
    assert result.records[0].source_view_sha256 == view.sha256()


@pytest.mark.parametrize("wrong", [0, -1, float("inf"), float("nan"), True, None, "60"])
def test_bad_freshness_budget_rejected(wrong):
    with pytest.raises(ValueError, match="positive"):
        replay(frame(), age=wrong)


@pytest.mark.parametrize("wrong", [0, -1, float("inf"), float("nan"), True, None, "60"])
def test_bad_gap_budget_rejected(wrong):
    with pytest.raises(ValueError, match="positive"):
        replay(frame(), gap=wrong)


@pytest.mark.parametrize("wrong", [[], (), [frame()], "not-frames", ("not-frame",)])
def test_nonimmutable_or_empty_frame_collection_rejected(wrong):
    with pytest.raises(ValueError, match="immutable"):
        replay_x5_history_v1(frames=wrong, max_age_seconds=60, max_step_seconds=60)


@pytest.mark.parametrize(
    "name",
    [
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ],
)
def test_frame_cannot_acquire_authority(name):
    with pytest.raises(ValueError, match="authority"):
        replace(frame(), **{name: True})


@pytest.mark.parametrize(
    "name",
    [
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
        "cross_frame_metric_comparison_allowed",
    ],
)
def test_record_cannot_acquire_authority(name):
    item = replay(frame()).records[0]
    with pytest.raises(ValueError, match="authority"):
        replace(item, **{name: True})


@pytest.mark.parametrize(
    "name",
    [
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
        "cross_frame_metric_comparison_allowed",
    ],
)
def test_result_cannot_acquire_authority(name):
    item = replay(frame())
    with pytest.raises(ValueError, match="authority"):
        replace(item, **{name: True})


@pytest.mark.parametrize("cls", [X5ReplayFrameV1, X5ReplayRecordV1, X5ReplayResultV1])
def test_all_replay_contracts_are_immutable(cls):
    r = replay(frame())
    item = {X5ReplayFrameV1: frame(), X5ReplayRecordV1: r.records[0], X5ReplayResultV1: r}[cls]
    with pytest.raises(FrozenInstanceError):
        item.data_only = False


@pytest.mark.parametrize("class_name", ["frame", "record", "result"])
@pytest.mark.parametrize("field", ["execution_authority", "data_only", "live_execution_eligible"])
def test_authority_flag_int_zero_is_rejected(class_name, field):
    value = frame() if class_name == "frame" else replay(frame())
    if class_name == "record":
        value = value.records[0]
    with pytest.raises(ValueError, match="exact booleans"):
        replace(value, **{field: 0})


def test_duplicate_replay_available_metric_rejected():
    record = replay(frame()).records[0]
    with pytest.raises(ValueError, match="available metrics"):
        replace(record, available_metrics=("PCR_OI", "PCR_OI"))


def test_forged_replay_research_status_rejected():
    record = replay(frame()).records[0]
    with pytest.raises(ValueError, match="status"):
        replace(record, research_status="UNAVAILABLE")


def test_bad_frame_schema_rejected():
    with pytest.raises(ValueError, match="authority"):
        replace(frame(), schema_version="UNVERSIONED")


def test_bad_record_schema_rejected():
    with pytest.raises(ValueError, match="authority"):
        replace(replay(frame()).records[0], schema_version="UNVERSIONED")


def test_bad_result_schema_rejected():
    with pytest.raises(ValueError, match="authority"):
        replace(replay(frame()), schema_version="UNVERSIONED")


def test_result_counts_cannot_be_fabricated():
    r = replay(frame())
    with pytest.raises(ValueError, match="count"):
        replace(r, source_frame_count=5)


def test_last_record_hash_cannot_be_fabricated():
    r = replay(frame())
    with pytest.raises(ValueError, match="last-record"):
        replace(r, last_record_sha256="a" * 64)


def test_result_rejects_relinked_record_even_with_updated_final_hash():
    c = capture()
    r = replay(frame(c), frame(next_capture(c)))
    mutated_record = replace(r.records[1], previous_record_sha256="b" * 64)
    with pytest.raises(ValueError, match="hash-chain"):
        replace(
            r, records=(r.records[0], mutated_record), last_record_sha256=mutated_record.sha256()
        )


def test_result_rejects_invalid_first_link_even_when_hash_updated():
    r = replay(frame())
    mutated = replace(r.records[0], previous_record_sha256="c" * 64)
    with pytest.raises(ValueError, match="hash-chain"):
        replace(r, records=(mutated,), last_record_sha256=mutated.sha256())


def test_result_rejects_swapped_record_order_even_with_new_last_hash():
    c = capture()
    r = replay(frame(c), frame(next_capture(c)))
    with pytest.raises(ValueError, match="hash-chain|increasing"):
        replace(r, records=tuple(reversed(r.records)), last_record_sha256=r.records[0].sha256())


def test_result_rejects_duplicate_capture_in_manually_constructed_records():
    c = capture()
    r = replay(frame(c), frame(next_capture(c)))
    second = replace(
        r.records[1],
        capture_id=r.records[0].capture_id,
        previous_record_sha256=r.records[0].sha256(),
    )
    with pytest.raises(ValueError, match="Duplicate replay record capture"):
        replace(r, records=(r.records[0], second), last_record_sha256=second.sha256())


def test_record_hash_chain_changes_if_source_changes():
    c = capture()
    a = replay(frame(c), frame(next_capture(c)))
    updated = next_capture(
        c,
        observations=tuple(
            replace(x, source_record_id=x.source_record_id + ":NEW", ltp=x.ltp + 1)
            for x in c.observations
        ),
    )
    b = replay(frame(c), frame(updated))
    assert a.last_record_sha256 != b.last_record_sha256
    assert a.sha256() != b.sha256()


def test_ordered_replay_is_deterministic():
    c = capture()
    sources = (frame(c), frame(next_capture(c)))
    assert replay(*sources).sha256() == replay(*sources).sha256()
    assert replay(*sources).records == replay(*sources).records


def test_reordered_option_rows_do_not_change_replay_hash():
    c = capture()
    shuffled = replace(c, observations=tuple(reversed(c.observations)))
    assert frame(c).expected_row_seals == frame(shuffled).expected_row_seals
    assert replay(frame(c)).sha256() == replay(frame(shuffled)).sha256()


def test_timezone_equivalent_checkpoints_replay_equally():
    from services.x5.contracts_v1 import IST

    c = capture()
    other = replace(
        c,
        as_of=c.as_of.astimezone(IST),
        captured_at=c.captured_at.astimezone(IST),
        observations=tuple(
            replace(x, observed_at=x.observed_at.astimezone(IST)) for x in c.observations
        ),
    )
    assert c.sha256() == other.sha256()
    assert replay(frame(c)).sha256() == replay(frame(other)).sha256()


def test_frame_row_seals_are_ordered_and_match_canonical_observations():
    sealed = frame()
    assert sealed.expected_row_seals == tuple(
        sorted(
            (x.source_record_id, canonical_sha256(asdict(x))) for x in sealed.capture.observations
        )
    )
    assert replay(sealed).records[0].row_seals_sha256 == canonical_sha256(sealed.expected_row_seals)


def test_static_replay_module_has_no_network_order_or_paper_imports():
    path = Path("services/x5/replay_provenance_v1.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    prohibited = (
        "services.broker",
        "services.execution",
        "services.paper",
        "src.mcx",
        "socket",
        "subprocess",
        "fyers_apiv3",
        "SmartApi",
    )
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports += [x.name for x in node.names]
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not [
        name for name in imports if any(name == p or name.startswith(p + ".") for p in prohibited)
    ]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            method = getattr(node.func, "attr", getattr(node.func, "id", ""))
            assert method not in {"place_order", "placeOrder", "submit_order", "send_order"}


def test_result_carries_no_trade_or_directional_aggregate():
    r = replay(frame())
    for key in (
        "order",
        "trade_action",
        "selected_contract",
        "aggregate_bias",
        "accuracy_score",
        "paper_trade_count",
        "certification_progress",
    ):
        assert key not in r.__dataclass_fields__
        assert key not in r.records[0].__dataclass_fields__

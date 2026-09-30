from __future__ import annotations

import ast
import inspect

from dataclasses import (
    fields,
    replace,
)
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest

from services.contracts.brain_evidence_v1 import (
    AnalyzerResultV1,
    EvidenceV1,
)
from services.brain.analyzer_registry_v1 import (
    DEFAULT_ANALYZER_REGISTRY_V1,
    SUPPORTED_MARKETS,
)
from services.brain.market_snapshot_v1 import (
    MarketSnapshotV1,
    build_market_snapshot_v1,
)
from services.brain.shadow_composer_v1 import (
    compose_shadow_brain_v1,
)
from services.brain.snapshot_persistence_v1 import (
    replay_snapshot_record_v1,
    serialize_snapshot_record_v1,
)


STAMP = datetime(
    2026,
    9,
    30,
    12,
    0,
    tzinfo=timezone.utc,
)


MARKETS = (
    "NIFTY",
    "SENSEX",
    "CRUDEOILM",
    "GOLDM",
    "NATGASMINI",
)


MCX_MARKETS = (
    "CRUDEOILM",
    "GOLDM",
    "NATGASMINI",
)


def _descriptors(
    market,
    *,
    production_only=False,
):
    values = tuple(
        descriptor
        for descriptor
        in DEFAULT_ANALYZER_REGISTRY_V1.descriptors
        if market
        in descriptor.markets
        and (
            not production_only
            or descriptor.currently_consumed_by_production
        )
    )

    return tuple(
        sorted(
            values,
            key=lambda item:
                item.analyzer_id,
        )
    )


def _descriptor(
    market,
    analyzer,
):
    matches = tuple(
        descriptor
        for descriptor
        in _descriptors(
            market
        )
        if descriptor.analyzer_id
        == analyzer
    )

    assert len(
        matches
    ) == 1

    return matches[0]


def _evidence_settings(
    state,
):
    if state == "BULLISH":
        return (
            "AVAILABLE",
            "FRESH",
            "BULLISH",
        )

    if state == "BEARISH":
        return (
            "AVAILABLE",
            "FRESH",
            "BEARISH",
        )

    if state == "NON_DIRECTIONAL":
        return (
            "AVAILABLE",
            "FRESH",
            "NEUTRAL",
        )

    if state == "UNKNOWN":
        return (
            "UNVERIFIED",
            "UNKNOWN",
            "UNKNOWN",
        )

    raise ValueError(
        state
    )


def _make_result(
    *,
    market,
    analyzer,
    state="BULLISH",
    evidence_id=None,
    analyzer_version=None,
    evidence_count=1,
):
    descriptor = _descriptor(
        market,
        analyzer,
    )

    version = (
        descriptor.analyzer_version
        if analyzer_version is None
        else analyzer_version
    )

    (
        status,
        freshness,
        direction,
    ) = _evidence_settings(
        state
    )

    evidence = tuple(
        EvidenceV1(
            evidence_id=(
                evidence_id
                if evidence_id is not None
                else (
                    f"{market}:{analyzer}:"
                    f"{state}:{index}"
                )
            ),
            market=market,
            analyzer=analyzer,
            analyzer_version=version,
            category=descriptor.category,
            feature=f"COMPOSER_TEST_{index}",
            observed_at=STAMP,
            generated_at=STAMP,
            status=status,
            freshness=freshness,
            source="B4_STEP5C_TEST",
            direction=direction,
            source_authoritative=False,
        )
        for index
        in range(
            evidence_count
        )
    )

    return AnalyzerResultV1(
        result_id=(
            f"result:{market}:{analyzer}:"
            f"{state}:{evidence_count}"
        ),
        market=market,
        analyzer=analyzer,
        analyzer_version=version,
        generated_at=STAMP,
        status="OK",
        evidence=evidence,
    )


def _snapshot(
    *,
    market,
    category_state=None,
    production_categories=None,
    include_extra=False,
    extra_state="UNKNOWN",
):
    if category_state is None:
        category_state = {}

    selected = (
        None
        if production_categories is None
        else set(
            production_categories
        )
    )

    results = []

    for descriptor in _descriptors(
        market,
        production_only=True,
    ):
        if (
            selected is not None
            and descriptor.category
            not in selected
        ):
            continue

        state = category_state.get(
            descriptor.category,
            "BULLISH",
        )

        results.append(
            _make_result(
                market=market,
                analyzer=descriptor.analyzer_id,
                state=state,
            )
        )

    if include_extra:
        extra_descriptor = next(
            descriptor
            for descriptor
            in _descriptors(
                market
            )
            if not descriptor.currently_consumed_by_production
        )

        results.append(
            _make_result(
                market=market,
                analyzer=extra_descriptor.analyzer_id,
                state=extra_state,
            )
        )

    return build_market_snapshot_v1(
        market=market,
        snapshot_at=STAMP,
        generated_at=STAMP,
        analyzer_results=tuple(
            results
        ),
        source_strategy_version="STRATEGY_V1",
        source_policy_epoch="POLICY_EPOCH_V1",
        source_runtime_ref="RUNTIME_REF_V1",
    )


def _zero_snapshot(
    market,
):
    return build_market_snapshot_v1(
        market=market,
        snapshot_at=STAMP,
        generated_at=STAMP,
        analyzer_results=(),
        source_strategy_version="STRATEGY_V1",
        source_policy_epoch="POLICY_EPOCH_V1",
        source_runtime_ref="RUNTIME_REF_V1",
    )


def _forge_snapshot(
    snapshot,
    **changes,
):
    forged = object.__new__(
        MarketSnapshotV1
    )

    for field in fields(
        MarketSnapshotV1
    ):
        object.__setattr__(
            forged,
            field.name,
            changes.get(
                field.name,
                getattr(
                    snapshot,
                    field.name,
                ),
            ),
        )

    return forged


@pytest.mark.parametrize(
    "market",
    MARKETS,
)
def test_zero_coverage_all_five_fail_closed(
    market,
):
    snapshot = _zero_snapshot(
        market
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert snapshot.production_complete is False
    assert snapshot.production_coverage_pct == 0.0

    assert (
        result.hypothesis.hypothesis
        == "INSUFFICIENT_EVIDENCE"
    )

    assert result.hypothesis.confidence == 0.0


@pytest.mark.parametrize(
    "market",
    MARKETS,
)
def test_full_bullish_all_five(
    market,
):
    snapshot = _snapshot(
        market=market
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert snapshot.production_complete is True
    assert result.hypothesis.hypothesis == "BULLISH"


@pytest.mark.parametrize(
    "market",
    MARKETS,
)
def test_full_bearish_all_five(
    market,
):
    categories = {
        descriptor.category:
            "BEARISH"
        for descriptor
        in _descriptors(
            market,
            production_only=True,
        )
    }

    snapshot = _snapshot(
        market=market,
        category_state=categories,
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert result.hypothesis.hypothesis == "BEARISH"


@pytest.mark.parametrize(
    "market",
    MARKETS,
)
def test_full_non_directional_all_five(
    market,
):
    categories = {
        descriptor.category:
            "NON_DIRECTIONAL"
        for descriptor
        in _descriptors(
            market,
            production_only=True,
        )
    }

    snapshot = _snapshot(
        market=market,
        category_state=categories,
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert result.hypothesis.hypothesis == "NEUTRAL"


@pytest.mark.parametrize(
    "market",
    MCX_MARKETS,
)
def test_partial_four_of_six_bullish_is_directional(
    market,
):
    categories = tuple(
        sorted(
            {
                descriptor.category
                for descriptor
                in _descriptors(
                    market,
                    production_only=True,
                )
            }
        )
    )

    snapshot = _snapshot(
        market=market,
        production_categories=
            categories[:4],
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert snapshot.production_complete is False

    assert (
        result.hypothesis.hypothesis
        == "BULLISH"
    )


@pytest.mark.parametrize(
    "market",
    MCX_MARKETS,
)
def test_partial_three_of_six_bullish_is_insufficient(
    market,
):
    categories = tuple(
        sorted(
            {
                descriptor.category
                for descriptor
                in _descriptors(
                    market,
                    production_only=True,
                )
            }
        )
    )

    snapshot = _snapshot(
        market=market,
        production_categories=
            categories[:3],
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert (
        result.hypothesis.hypothesis
        == "INSUFFICIENT_EVIDENCE"
    )


@pytest.mark.parametrize(
    "market",
    MARKETS,
)
def test_result_snapshot_fields_are_exact(
    market,
):
    snapshot = _zero_snapshot(
        market
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert result.market == snapshot.market

    assert (
        result.snapshot_sha256
        == snapshot.snapshot_sha256
    )

    assert (
        result.snapshot_at
        == snapshot.snapshot_at
    )

    assert (
        result.generated_at
        == snapshot.generated_at
    )

    assert (
        result.source_strategy_version
        == snapshot.source_strategy_version
    )

    assert (
        result.source_policy_epoch
        == snapshot.source_policy_epoch
    )

    assert (
        result.source_runtime_ref
        == snapshot.source_runtime_ref
    )

    assert (
        result.production_coverage_pct
        == snapshot.production_coverage_pct
    )

    assert (
        result.production_complete
        == snapshot.production_complete
    )

    assert (
        result.missing_production_analyzers
        == snapshot.missing_production_analyzers
    )


@pytest.mark.parametrize(
    "market",
    MARKETS,
)
def test_result_authorities_are_always_false(
    market,
):
    result = compose_shadow_brain_v1(
        _zero_snapshot(
            market
        )
    )

    assert result.execution_authority is False
    assert result.decision_authority is False
    assert result.risk_authority is False
    assert result.position_authority is False
    assert result.certification_authority is False


@pytest.mark.parametrize(
    "field_name",
    (
        "source_strategy_version",
        "source_policy_epoch",
        "source_runtime_ref",
    ),
)
def test_none_provenance_is_rejected(
    field_name,
):
    snapshot = _zero_snapshot(
        "NIFTY"
    )

    invalid = replace(
        snapshot,
        **{
            field_name:
                None
        },
    )

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        compose_shadow_brain_v1(
            invalid
        )


def test_incomplete_expected_production_set_is_rejected():
    snapshot = _zero_snapshot(
        "NIFTY"
    )

    invalid = replace(
        snapshot,
        expected_production_analyzers=
            snapshot.expected_production_analyzers[:-1],
    )

    with pytest.raises(
        ValueError,
        match="expected_production_analyzers",
    ):
        compose_shadow_brain_v1(
            invalid
        )


def test_wrong_registry_schema_is_rejected():
    snapshot = _zero_snapshot(
        "NIFTY"
    )

    invalid = replace(
        snapshot,
        registry_schema_version="FORGED_SCHEMA",
    )

    with pytest.raises(
        ValueError,
        match="registry_schema_version",
    ):
        compose_shadow_brain_v1(
            invalid
        )


@pytest.mark.parametrize(
    "authority_field",
    (
        "execution_authority",
        "decision_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
    ),
)
def test_forged_true_snapshot_authority_is_rejected(
    authority_field,
):
    snapshot = _zero_snapshot(
        "NIFTY"
    )

    invalid = _forge_snapshot(
        snapshot,
        **{
            authority_field:
                True
        },
    )

    with pytest.raises(
        ValueError
    ):
        compose_shadow_brain_v1(
            invalid
        )


def test_registered_shadow_extra_does_not_drive_hypothesis():
    baseline = _snapshot(
        market="NIFTY"
    )

    with_extra = _snapshot(
        market="NIFTY",
        include_extra=True,
        extra_state="BEARISH",
    )

    first = compose_shadow_brain_v1(
        baseline
    )

    second = compose_shadow_brain_v1(
        with_extra
    )

    assert first.hypothesis.hypothesis == "BULLISH"
    assert second.hypothesis.hypothesis == "BULLISH"


def test_registered_shadow_extra_remains_bound_by_snapshot_hash():
    baseline = _snapshot(
        market="NIFTY"
    )

    with_extra = _snapshot(
        market="NIFTY",
        include_extra=True,
        extra_state="UNKNOWN",
    )

    first = compose_shadow_brain_v1(
        baseline
    )

    second = compose_shadow_brain_v1(
        with_extra
    )

    assert (
        baseline.snapshot_sha256
        != with_extra.snapshot_sha256
    )

    assert (
        first.snapshot_sha256
        == baseline.snapshot_sha256
    )

    assert (
        second.snapshot_sha256
        == with_extra.snapshot_sha256
    )


def test_quality_metadata_includes_registered_shadow_extra():
    snapshot = _snapshot(
        market="NIFTY",
        include_extra=True,
        extra_state="UNKNOWN",
    )

    extra_ids = {
        evidence.evidence_id
        for result
        in snapshot.analyzer_results
        if result.analyzer
        == "canonical.technical_intelligence.v1"
        for evidence
        in result.evidence
    }

    assert extra_ids

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert extra_ids.issubset(
        set(
            result.unverified_evidence_ids
        )
    )


def test_quality_metadata_uses_exact_status_and_freshness():
    production = _make_result(
        market="CRUDEOILM",
        analyzer="mcx.mtf.native_v1",
        state="UNKNOWN",
    )

    snapshot = build_market_snapshot_v1(
        market="CRUDEOILM",
        snapshot_at=STAMP,
        generated_at=STAMP,
        analyzer_results=(
            production,
        ),
        source_strategy_version="STRATEGY_V1",
        source_policy_epoch="POLICY_EPOCH_V1",
        source_runtime_ref="RUNTIME_REF_V1",
    )

    evidence_id = (
        production.evidence[0].evidence_id
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert result.unverified_evidence_ids == (
        evidence_id,
    )

    assert result.stale_evidence_ids == ()


def test_stale_metadata_is_independent_of_unverified_metadata():
    descriptor = _descriptor(
        "CRUDEOILM",
        "mcx.mtf.native_v1",
    )

    evidence = EvidenceV1(
        evidence_id="stale-but-available",
        market="CRUDEOILM",
        analyzer=descriptor.analyzer_id,
        analyzer_version=descriptor.analyzer_version,
        category=descriptor.category,
        feature="STALE_TEST",
        observed_at=STAMP,
        generated_at=STAMP,
        status="AVAILABLE",
        freshness="STALE",
        source="B4_STEP5C_TEST",
        direction="BULLISH",
    )

    analyzer = AnalyzerResultV1(
        result_id="stale-result",
        market="CRUDEOILM",
        analyzer=descriptor.analyzer_id,
        analyzer_version=descriptor.analyzer_version,
        generated_at=STAMP,
        status="OK",
        evidence=(
            evidence,
        ),
    )

    snapshot = build_market_snapshot_v1(
        market="CRUDEOILM",
        snapshot_at=STAMP,
        generated_at=STAMP,
        analyzer_results=(
            analyzer,
        ),
        source_strategy_version="STRATEGY_V1",
        source_policy_epoch="POLICY_EPOCH_V1",
        source_runtime_ref="RUNTIME_REF_V1",
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert result.unverified_evidence_ids == ()

    assert result.stale_evidence_ids == (
        "stale-but-available",
    )


def test_global_duplicate_evidence_id_is_rejected():
    first = _make_result(
        market="NIFTY",
        analyzer="index.mtf.legacy_v1",
        evidence_id="duplicate-global-id",
    )

    second = _make_result(
        market="NIFTY",
        analyzer="canonical.technical_intelligence.v1",
        state="UNKNOWN",
        evidence_id="duplicate-global-id",
    )

    base = _zero_snapshot(
        "NIFTY"
    )

    forged = _forge_snapshot(
        base,
        analyzer_results=(
            first,
            second,
        ),
    )

    with pytest.raises(
        ValueError,
        match="globally unique",
    ):
        compose_shadow_brain_v1(
            forged
        )


def test_unregistered_analyzer_is_rejected():
    evidence = EvidenceV1(
        evidence_id="fake-evidence",
        market="NIFTY",
        analyzer="fake.analyzer.v1",
        analyzer_version="1.0",
        category="TECHNICAL",
        feature="FAKE",
        observed_at=STAMP,
        generated_at=STAMP,
        status="AVAILABLE",
        freshness="FRESH",
        source="B4_STEP5C_TEST",
        direction="BULLISH",
    )

    analyzer = AnalyzerResultV1(
        result_id="fake-result",
        market="NIFTY",
        analyzer="fake.analyzer.v1",
        analyzer_version="1.0",
        generated_at=STAMP,
        status="OK",
        evidence=(
            evidence,
        ),
    )

    base = _zero_snapshot(
        "NIFTY"
    )

    forged = _forge_snapshot(
        base,
        analyzer_results=(
            analyzer,
        ),
    )

    with pytest.raises(
        ValueError,
        match="unregistered analyzer",
    ):
        compose_shadow_brain_v1(
            forged
        )


@pytest.mark.parametrize(
    "analyzer",
    (
        "index.mtf.legacy_v1",
        "canonical.technical_intelligence.v1",
    ),
)
def test_forged_evidence_category_mismatch_is_rejected(
    analyzer,
):
    valid_result = _make_result(
        market="NIFTY",
        analyzer=analyzer,
    )

    original_evidence = (
        valid_result.evidence[0]
    )

    descriptor = _descriptor(
        "NIFTY",
        analyzer,
    )

    wrong_category = (
        "OPTIONS"
        if descriptor.category
        != "OPTIONS"
        else "TECHNICAL"
    )

    forged_evidence = object.__new__(
        EvidenceV1
    )

    for field in fields(
        EvidenceV1
    ):
        object.__setattr__(
            forged_evidence,
            field.name,
            (
                wrong_category
                if field.name
                == "category"
                else getattr(
                    original_evidence,
                    field.name,
                )
            ),
        )

    forged_result = object.__new__(
        AnalyzerResultV1
    )

    for field in fields(
        AnalyzerResultV1
    ):
        object.__setattr__(
            forged_result,
            field.name,
            (
                (
                    forged_evidence,
                )
                if field.name
                == "evidence"
                else getattr(
                    valid_result,
                    field.name,
                )
            ),
        )

    base = _zero_snapshot(
        "NIFTY"
    )

    forged_snapshot = _forge_snapshot(
        base,
        analyzer_results=(
            forged_result,
        ),
    )

    with pytest.raises(
        ValueError,
        match="evidence category",
    ):
        compose_shadow_brain_v1(
            forged_snapshot
        )


def test_registered_analyzer_wrong_version_is_rejected():
    wrong = _make_result(
        market="CRUDEOILM",
        analyzer="mcx.mtf.native_v1",
        analyzer_version="999.0",
    )

    base = _zero_snapshot(
        "CRUDEOILM"
    )

    forged = _forge_snapshot(
        base,
        analyzer_results=(
            wrong,
        ),
    )

    with pytest.raises(
        ValueError,
        match="version",
    ):
        compose_shadow_brain_v1(
            forged
        )


def test_non_snapshot_input_is_rejected():
    with pytest.raises(
        TypeError,
        match="MarketSnapshotV1",
    ):
        compose_shadow_brain_v1(
            object()
        )


def test_same_snapshot_produces_identical_result():
    snapshot = _snapshot(
        market="GOLDM"
    )

    first = compose_shadow_brain_v1(
        snapshot
    )

    second = compose_shadow_brain_v1(
        snapshot
    )

    assert first == second


def test_serialized_replay_produces_identical_shadow_result():
    snapshot = _snapshot(
        market="CRUDEOILM"
    )

    record = serialize_snapshot_record_v1(
        snapshot
    )

    replayed = replay_snapshot_record_v1(
        record
    )

    first = compose_shadow_brain_v1(
        snapshot
    )

    second = compose_shadow_brain_v1(
        replayed
    )

    assert first == second


def test_result_generated_at_is_snapshot_generated_at_not_new_clock_value():
    snapshot = _zero_snapshot(
        "NATGASMINI"
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert result.generated_at == STAMP


def test_provenance_values_are_preserved_exactly():
    snapshot = build_market_snapshot_v1(
        market="GOLDM",
        snapshot_at=STAMP,
        generated_at=STAMP,
        analyzer_results=(),
        source_strategy_version="Strategy-Exact-01",
        source_policy_epoch="Epoch-Exact-02",
        source_runtime_ref="Runtime-Exact-03",
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert (
        result.source_strategy_version
        == "Strategy-Exact-01"
    )

    assert (
        result.source_policy_epoch
        == "Epoch-Exact-02"
    )

    assert (
        result.source_runtime_ref
        == "Runtime-Exact-03"
    )


def test_partial_missing_production_analyzers_preserved_exactly():
    snapshot = _snapshot(
        market="CRUDEOILM",
        production_categories=(
            "EVENT",
            "OPTIONS",
        ),
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    assert (
        result.missing_production_analyzers
        == snapshot.missing_production_analyzers
    )

    assert result.production_complete is False

    assert (
        result.production_coverage_pct
        == snapshot.production_coverage_pct
    )


def test_extra_evidence_multiplicity_cannot_change_hypothesis():
    baseline = _snapshot(
        market="NIFTY"
    )

    extra_descriptor = _descriptor(
        "NIFTY",
        "canonical.technical_intelligence.v1",
    )

    extra = _make_result(
        market="NIFTY",
        analyzer=extra_descriptor.analyzer_id,
        state="UNKNOWN",
        evidence_count=100,
    )

    expanded = build_market_snapshot_v1(
        market="NIFTY",
        snapshot_at=STAMP,
        generated_at=STAMP,
        analyzer_results=(
            baseline.analyzer_results
            + (
                extra,
            )
        ),
        source_strategy_version="STRATEGY_V1",
        source_policy_epoch="POLICY_EPOCH_V1",
        source_runtime_ref="RUNTIME_REF_V1",
    )

    first = compose_shadow_brain_v1(
        baseline
    )

    second = compose_shadow_brain_v1(
        expanded
    )

    assert first.hypothesis.hypothesis == "BULLISH"
    assert second.hypothesis.hypothesis == "BULLISH"

    assert len(
        second.unverified_evidence_ids
    ) >= 100


def test_composer_public_signature_is_snapshot_only():
    signature = inspect.signature(
        compose_shadow_brain_v1
    )

    assert tuple(
        signature.parameters
    ) == (
        "snapshot",
    )


def test_composer_import_surface_has_no_external_provider_or_runtime_dependencies():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_composer_v1.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    imports = []

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            imports.extend(
                alias.name.lower()
                for alias
                in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            imports.append(
                (
                    node.module
                    or ""
                ).lower()
            )

    forbidden = (
        "fyers",
        "smartapi",
        "requests",
        "yfinance",
        "broker",
        "paper_orchestration",
        "capture_coordinator",
        "snapshot_persistence",
        "snapshot_journal",
    )

    assert not any(
        token in module
        for module
        in imports
        for token
        in forbidden
    )


def test_composer_has_no_clock_random_trade_or_pnl_surface():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_composer_v1.py"
    )

    source = path.read_text(
        encoding="utf-8"
    ).lower()

    forbidden = (
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "random.",
        "buy_call",
        "buy_put",
        "strike_selection",
        "quantity_selection",
        "stop_loss",
        "target_1",
        "target_2",
        "target_3",
        "profit_factor",
        "win_rate",
        "pnl",
    )

    assert not any(
        token in source
        for token
        in forbidden
    )
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from services.brain.shadow_brain_v1 import (
    SHADOW_BRAIN_RESULT_SCHEMA_V1,
    SHADOW_HYPOTHESIS_SCHEMA_V1,
    SHADOW_HYPOTHESES,
    ShadowBrainResultV1,
    ShadowHypothesisV1,
)


NOW = datetime(
    2026,
    9,
    30,
    15,
    0,
    tzinfo=timezone.utc,
)


def _hypothesis(
    **changes,
) -> ShadowHypothesisV1:
    values = {
        "market": "NIFTY",
        "hypothesis": "NEUTRAL",
        "confidence": 0.5,
        "supporting_evidence_ids": ("e1",),
        "opposing_evidence_ids": ("e2",),
        "unknown_evidence_ids": ("e3",),
        "rationale_codes": ("BALANCED_EVIDENCE",),
    }

    values.update(changes)

    return ShadowHypothesisV1(
        **values
    )


def _result(
    **changes,
) -> ShadowBrainResultV1:
    hypothesis = changes.pop(
        "hypothesis",
        _hypothesis(),
    )

    values = {
        "market": "NIFTY",
        "snapshot_sha256": "a" * 64,
        "snapshot_at": NOW,
        "generated_at": NOW,
        "source_strategy_version": "NS_DESIGN_B_BID_AUTH_V4",
        "source_policy_epoch": "NS_CERT_20260929_V4",
        "source_runtime_ref": "R2.2",
        "production_coverage_pct": 90.0,
        "production_complete": False,
        "missing_production_analyzers": (
            "index.event_calendar.legacy_v1",
        ),
        "unverified_evidence_ids": ("e3",),
        "stale_evidence_ids": (),
    }

    values.update(changes)

    return ShadowBrainResultV1(
        hypothesis=hypothesis,
        **values
    )


def test_valid_contracts_are_json_serializable():
    hypothesis = _hypothesis()
    result = _result(
        hypothesis=hypothesis
    )

    hypothesis_json = json.dumps(
        hypothesis.to_dict(),
        sort_keys=True,
    )

    result_json = json.dumps(
        result.to_dict(),
        sort_keys=True,
    )

    assert hypothesis.schema_version == SHADOW_HYPOTHESIS_SCHEMA_V1
    assert result.schema_version == SHADOW_BRAIN_RESULT_SCHEMA_V1
    assert isinstance(hypothesis_json, str)
    assert isinstance(result_json, str)


def test_shadow_hypothesis_is_frozen():
    hypothesis = _hypothesis()

    with pytest.raises(
        FrozenInstanceError,
    ):
        hypothesis.confidence = 0.8


def test_shadow_result_is_frozen():
    result = _result()

    with pytest.raises(
        FrozenInstanceError,
    ):
        result.market = "SENSEX"


@pytest.mark.parametrize(
    "market",
    (
        "NIFTY",
        "SENSEX",
        "CRUDEOILM",
        "GOLDM",
        "NATGASMINI",
    ),
)
def test_all_five_markets_are_supported(
    market,
):
    hypothesis = _hypothesis(
        market=market
    )

    result = _result(
        market=market,
        hypothesis=hypothesis,
    )

    assert hypothesis.market == market
    assert result.market == market


def test_invalid_hypothesis_market_is_rejected():
    with pytest.raises(
        ValueError,
        match="unsupported shadow market",
    ):
        _hypothesis(
            market="BANKNIFTY"
        )


def test_invalid_hypothesis_enum_is_rejected():
    with pytest.raises(
        ValueError,
        match="unsupported shadow hypothesis",
    ):
        _hypothesis(
            hypothesis="BUY_CALL"
        )


@pytest.mark.parametrize(
    "confidence",
    (
        -0.1,
        1.1,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
    ),
)
def test_invalid_confidence_is_rejected(
    confidence,
):
    with pytest.raises(
        ValueError,
        match="confidence must be finite",
    ):
        _hypothesis(
            confidence=confidence
        )


@pytest.mark.parametrize(
    "confidence",
    (
        0.0,
        1.0,
    ),
)
def test_confidence_boundaries_are_valid(
    confidence,
):
    hypothesis = _hypothesis(
        confidence=confidence
    )

    assert hypothesis.confidence == confidence


def test_evidence_id_collection_must_be_tuple():
    with pytest.raises(
        TypeError,
        match="must be a tuple",
    ):
        _hypothesis(
            supporting_evidence_ids=["e1"]
        )


def test_duplicate_evidence_ids_are_rejected():
    with pytest.raises(
        ValueError,
        match="must not contain duplicates",
    ):
        _hypothesis(
            supporting_evidence_ids=(
                "e1",
                "e1",
            )
        )


def test_unsorted_evidence_ids_are_rejected():
    with pytest.raises(
        ValueError,
        match="must be sorted",
    ):
        _hypothesis(
            supporting_evidence_ids=(
                "e2",
                "e1",
            )
        )


def test_blank_evidence_id_is_rejected():
    with pytest.raises(
        ValueError,
        match="non-empty trimmed string",
    ):
        _hypothesis(
            supporting_evidence_ids=("",)
        )


@pytest.mark.parametrize(
    "changes, message",
    (
        (
            {
                "supporting_evidence_ids": ("same",),
                "opposing_evidence_ids": ("same",),
            },
            "supporting and opposing",
        ),
        (
            {
                "supporting_evidence_ids": ("same",),
                "unknown_evidence_ids": ("same",),
            },
            "supporting and unknown",
        ),
        (
            {
                "opposing_evidence_ids": ("same",),
                "unknown_evidence_ids": ("same",),
            },
            "opposing and unknown",
        ),
    ),
)
def test_evidence_role_sets_must_be_disjoint(
    changes,
    message,
):
    with pytest.raises(
        ValueError,
        match=message,
    ):
        _hypothesis(
            **changes
        )


def test_hypothesis_schema_mismatch_is_rejected():
    with pytest.raises(
        ValueError,
        match="unsupported ShadowHypothesisV1 schema",
    ):
        _hypothesis(
            schema_version="BRAIN_SHADOW_HYPOTHESIS_V2"
        )


def test_invalid_result_market_is_rejected():
    with pytest.raises(
        ValueError,
        match="unsupported shadow market",
    ):
        _result(
            market="BANKNIFTY"
        )


@pytest.mark.parametrize(
    "snapshot_sha256",
    (
        "a" * 63,
        "A" * 64,
        "g" * 64,
        123,
    ),
)
def test_malformed_snapshot_hash_is_rejected(
    snapshot_sha256,
):
    with pytest.raises(
        ValueError,
        match="snapshot_sha256",
    ):
        _result(
            snapshot_sha256=snapshot_sha256
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "snapshot_at",
        "generated_at",
    ),
)
def test_naive_result_timestamps_are_rejected(
    field_name,
):
    naive = NOW.replace(
        tzinfo=None
    )

    with pytest.raises(
        ValueError,
        match=f"{field_name} must be timezone-aware",
    ):
        _result(
            **{
                field_name: naive
            }
        )


def test_generated_time_cannot_precede_snapshot_time():
    with pytest.raises(
        ValueError,
        match="generated_at must not precede snapshot_at",
    ):
        _result(
            generated_at=(
                NOW
                - timedelta(seconds=1)
            )
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "source_strategy_version",
        "source_policy_epoch",
        "source_runtime_ref",
    ),
)
def test_blank_source_identity_is_rejected(
    field_name,
):
    with pytest.raises(
        ValueError,
        match="non-empty trimmed string",
    ):
        _result(
            **{
                field_name: ""
            }
        )


@pytest.mark.parametrize(
    "coverage",
    (
        -0.1,
        100.1,
        float("nan"),
        float("inf"),
        True,
    ),
)
def test_invalid_production_coverage_is_rejected(
    coverage,
):
    with pytest.raises(
        ValueError,
        match="production_coverage_pct must be finite",
    ):
        _result(
            production_coverage_pct=coverage
        )


def test_production_complete_must_be_bool():
    with pytest.raises(
        TypeError,
        match="production_complete must be bool",
    ):
        _result(
            production_complete=1
        )


def test_complete_result_requires_100_percent_coverage():
    with pytest.raises(
        ValueError,
        match="complete production coverage must equal 100.0",
    ):
        _result(
            production_complete=True,
            production_coverage_pct=99.0,
            missing_production_analyzers=(),
        )


def test_complete_result_cannot_have_missing_analyzers():
    with pytest.raises(
        ValueError,
        match="cannot have missing analyzers",
    ):
        _result(
            production_complete=True,
            production_coverage_pct=100.0,
            missing_production_analyzers=(
                "index.event_calendar.legacy_v1",
            ),
        )


def test_incomplete_result_must_be_below_100_percent():
    with pytest.raises(
        ValueError,
        match="incomplete production coverage must be below 100.0",
    ):
        _result(
            production_complete=False,
            production_coverage_pct=100.0,
            missing_production_analyzers=(
                "index.event_calendar.legacy_v1",
            ),
        )


def test_incomplete_result_requires_missing_analyzers():
    with pytest.raises(
        ValueError,
        match="requires missing analyzers",
    ):
        _result(
            production_complete=False,
            production_coverage_pct=90.0,
            missing_production_analyzers=(),
        )


def test_hypothesis_must_be_correct_contract_type():
    with pytest.raises(
        TypeError,
        match="hypothesis must be ShadowHypothesisV1",
    ):
        _result(
            hypothesis="NEUTRAL"
        )


def test_hypothesis_market_must_match_result_market():
    with pytest.raises(
        ValueError,
        match="hypothesis market must equal result market",
    ):
        _result(
            market="SENSEX",
            hypothesis=_hypothesis(
                market="NIFTY"
            ),
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "execution_authority",
        "decision_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
    ),
)
def test_authority_promotion_is_rejected(
    field_name,
):
    result = _result()

    with pytest.raises(
        ValueError,
        match="permanently False",
    ):
        replace(
            result,
            **{
                field_name: True
            },
        )


def test_result_schema_mismatch_is_rejected():
    with pytest.raises(
        ValueError,
        match="unsupported ShadowBrainResultV1 schema",
    ):
        _result(
            schema_version="BRAIN_SHADOW_RESULT_V2"
        )


def test_equivalent_results_have_identical_canonical_hash():
    first = _result()
    second = _result()

    assert first.canonical_json() == second.canonical_json()
    assert first.shadow_result_sha256 == second.shadow_result_sha256
    assert len(first.shadow_result_sha256) == 64


def test_material_result_change_changes_hash():
    first = _result()

    second = _result(
        hypothesis=_hypothesis(
            confidence=0.6
        )
    )

    assert first.canonical_json() != second.canonical_json()
    assert first.shadow_result_sha256 != second.shadow_result_sha256


def test_canonical_json_matches_exact_sorted_compact_encoding():
    result = _result()

    expected = json.dumps(
        result.to_dict(),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    assert result.canonical_json() == expected


def test_output_surface_contains_no_trade_or_pnl_fields():
    contract_fields = [
        field.name
        for cls in (
            ShadowHypothesisV1,
            ShadowBrainResultV1,
        )
        for field in fields(cls)
    ]

    banned = {
        "action",
        "recommendation",
        "signal",
        "order",
        "broker",
        "strike",
        "quantity",
        "qty",
        "sl",
        "stop",
        "loss",
        "target",
        "call",
        "put",
        "buy",
        "sell",
        "pnl",
        "profit",
    }

    bad = [
        name
        for name in contract_fields
        if any(
            token in banned
            for token in name.lower().split("_")
        )
    ]

    result = _result()
    payload = result.to_dict()

    assert bad == []
    assert payload["execution_authority"] is False
    assert payload["decision_authority"] is False
    assert payload["risk_authority"] is False
    assert payload["position_authority"] is False
    assert payload["certification_authority"] is False


def test_shadow_contract_module_has_no_provider_or_broker_imports():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_brain_v1.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )

    imports = []

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            imports.extend(
                alias.name.lower()
                for alias in node.names
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
        "execution",
    )

    assert not any(
        token in module
        for module in imports
        for token in forbidden
    )


def test_hypothesis_enum_is_exact_and_contains_no_trade_action():
    assert SHADOW_HYPOTHESES == frozenset(
        {
            "BULLISH",
            "BEARISH",
            "NEUTRAL",
            "INSUFFICIENT_EVIDENCE",
        }
    )

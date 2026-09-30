from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from services.contracts.brain_evidence_v1 import (
    AnalyzerResultV1,
    EvidenceV1,
)


NOW = datetime(
    2026,
    9,
    30,
    6,
    30,
    tzinfo=timezone.utc,
)


def make_evidence(
    **overrides,
):
    values = {
        "evidence_id":
            "EV-NIFTY-RSI-1",

        "market":
            "NIFTY",

        "analyzer":
            "legacy_index_mtf_adapter",

        "analyzer_version":
            "1.0",

        "category":
            "MOMENTUM",

        "feature":
            "RSI_5M",

        "observed_at":
            NOW,

        "generated_at":
            NOW,

        "status":
            "AVAILABLE",

        "freshness":
            "FRESH",

        "source":
            "FYERS",

        "value":
            57.2,

        "unit":
            "INDEX",

        "direction":
            "BULLISH",

        "strength":
            0.57,

        "confidence":
            0.80,

        "quality_score":
            1.0,

        "source_authoritative":
            True,

        "metadata":
            (
                (
                    "timeframe",
                    "5m",
                ),
            ),
    }

    values.update(
        overrides
    )

    return EvidenceV1(
        **values
    )


def test_evidence_accepts_canonical_observation():
    evidence = make_evidence()

    assert evidence.market == "NIFTY"
    assert evidence.feature == "RSI_5M"
    assert evidence.value == 57.2
    assert evidence.direction == "BULLISH"
    assert evidence.source_authoritative is True


def test_evidence_serializes_to_json_safe_dict():
    payload = make_evidence().to_dict()

    encoded = json.dumps(
        payload,
        sort_keys=True,
    )

    assert "BRAIN_EVIDENCE_V1" in encoded
    assert payload["metadata"] == {
        "timeframe":
            "5m"
    }


def test_evidence_requires_timezone_aware_times():
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        make_evidence(
            observed_at=datetime(
                2026,
                9,
                30,
                12,
                0,
            )
        )


def test_evidence_requires_unavailable_reason():
    with pytest.raises(
        ValueError,
        match="requires missing_reason",
    ):
        make_evidence(
            status="UNAVAILABLE",
            value=None,
        )


def test_unavailable_evidence_can_fail_closed_explicitly():
    evidence = make_evidence(
        status="UNAVAILABLE",
        freshness="UNKNOWN",
        value=None,
        direction="UNKNOWN",
        strength=None,
        confidence=None,
        quality_score=0.0,
        source_authoritative=False,
        missing_reason="FUTURE_QUOTE_MISSING",
        blockers=(
            "FUTURE_QUOTE_MISSING",
        ),
    )

    assert evidence.status == "UNAVAILABLE"
    assert evidence.missing_reason == "FUTURE_QUOTE_MISSING"


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "strength",
            -0.01,
        ),
        (
            "confidence",
            1.01,
        ),
        (
            "quality_score",
            float("nan"),
        ),
    ],
)
def test_probability_fields_are_bounded(
    field,
    value,
):
    with pytest.raises(
        ValueError,
    ):
        make_evidence(
            **{
                field:
                    value
            }
        )


def test_metadata_keys_must_be_unique():
    with pytest.raises(
        ValueError,
        match="duplicate metadata key",
    ):
        make_evidence(
            metadata=(
                (
                    "timeframe",
                    "5m",
                ),
                (
                    "timeframe",
                    "15m",
                ),
            )
        )


def test_analyzer_result_requires_matching_evidence_authority():
    evidence = make_evidence()

    result = AnalyzerResultV1(
        result_id="AR-NIFTY-1",
        market="NIFTY",
        analyzer="legacy_index_mtf_adapter",
        analyzer_version="1.0",
        generated_at=NOW,
        status="OK",
        evidence=(
            evidence,
        ),
    )

    assert result.execution_authority is False
    assert result.evidence == (
        evidence,
    )


def test_analyzer_result_rejects_market_mismatch():
    evidence = make_evidence()

    with pytest.raises(
        ValueError,
        match="market",
    ):
        AnalyzerResultV1(
            result_id="AR-SENSEX-1",
            market="SENSEX",
            analyzer="legacy_index_mtf_adapter",
            analyzer_version="1.0",
            generated_at=NOW,
            status="OK",
            evidence=(
                evidence,
            ),
        )


def test_analyzer_result_can_never_receive_execution_authority():
    evidence = make_evidence()

    with pytest.raises(
        ValueError,
        match="permanently False",
    ):
        AnalyzerResultV1(
            result_id="AR-NIFTY-1",
            market="NIFTY",
            analyzer="legacy_index_mtf_adapter",
            analyzer_version="1.0",
            generated_at=NOW,
            status="OK",
            evidence=(
                evidence,
            ),
            execution_authority=True,
        )


def test_contract_contains_no_trade_action_fields():
    evidence_fields = set(
        EvidenceV1.__dataclass_fields__
    )

    analyzer_fields = set(
        AnalyzerResultV1.__dataclass_fields__
    )

    forbidden = {
        "action",
        "trade_action",
        "buy_call",
        "buy_put",
        "order",
        "order_id",
        "broker_submission",
        "position",
        "quantity",
        "lots",
    }

    assert not (
        evidence_fields
        & forbidden
    )

    assert not (
        analyzer_fields
        & forbidden
    )


def test_analyzer_result_is_json_serializable():
    result = AnalyzerResultV1(
        result_id="AR-NIFTY-1",
        market="NIFTY",
        analyzer="legacy_index_mtf_adapter",
        analyzer_version="1.0",
        generated_at=NOW,
        status="OK",
        evidence=(
            make_evidence(),
        ),
    )

    payload = result.to_dict()

    json.dumps(
        payload,
        sort_keys=True,
    )

    assert payload[
        "execution_authority"
    ] is False
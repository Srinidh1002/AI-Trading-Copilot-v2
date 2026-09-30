from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from services.brain.analyzer_registry_v1 import (
    DEFAULT_ANALYZER_REGISTRY_V1,
)
from services.brain.source_adapters_v1 import (
    IndexBreadthSourceV1,
    IndexNewsSourceV1,
    IndexOptionChainSourceV1,
    IndexPremarketSourceV1,
    IndexTechnicalSourceV1,
    McxEventRiskSourceV1,
    McxNativeSourceV1,
    adapt_index_breadth_v1,
    adapt_index_news_v1,
    adapt_index_option_chain_v1,
    adapt_index_premarket_v1,
    adapt_index_technical_v1,
    adapt_mcx_event_risk_v1,
    adapt_mcx_native_v1,
)


NOW = datetime(
    2026,
    9,
    30,
    8,
    0,
    tzinfo=timezone.utc,
)


def production_outputs():
    return (
        *adapt_index_premarket_v1(
            IndexPremarketSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
            )
        ),

        adapt_index_news_v1(
            IndexNewsSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
                status="AVAILABLE",
                freshness="FRESH",
                source="LEGACY_NEWS_ENGINE",
                sentiment="NEUTRAL",
                direction="NEUTRAL",
                bullish_count=0,
                bearish_count=0,
                headline_count=10,
                feeds_available=3,
                feeds_expected=3,
            )
        ),

        *adapt_index_technical_v1(
            IndexTechnicalSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
            )
        ),

        adapt_index_breadth_v1(
            IndexBreadthSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
                breadth_score=0.20,
                breadth_direction="BULLISH",
                advances=32,
                declines=17,
                unchanged=1,
                heavyweight_direction="MIXED",
            )
        ),

        adapt_index_option_chain_v1(
            IndexOptionChainSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
                pcr_value=0.30,
                pcr_direction="BULLISH",
                pcr_interpretation="INDEX_LEGACY_SOURCE_RULE",
                max_pain=22700.0,
                support=22600.0,
                resistance=22800.0,
                atm_strike=22700.0,
                expiry="2026-10-01",
                chain_coverage_pct=100.0,
            )
        ),

        *adapt_mcx_native_v1(
            McxNativeSourceV1(
                market="CRUDEOILM",
                observed_at=NOW,
                generated_at=NOW,
            )
        ),

        adapt_mcx_event_risk_v1(
            McxEventRiskSourceV1(
                market="CRUDEOILM",
                observed_at=NOW,
                generated_at=NOW,
                status="UNVERIFIED",
                freshness="UNKNOWN",
                event_state="NO_VERIFIED_BLOCK",
                source_authoritative=False,
                provider_block_entries=False,
                hard_block_eligible=False,
            )
        ),
    )


def test_breadth_adapter_preserves_source_values():
    result = adapt_index_breadth_v1(
        IndexBreadthSourceV1(
            market="NIFTY",
            observed_at=NOW,
            generated_at=NOW,
            breadth_score=0.42,
            breadth_direction="BULLISH",
            advances=35,
            declines=14,
            unchanged=1,
            heavyweight_direction="BULLISH",
        )
    )

    evidence = result.evidence[0]

    assert evidence.value == 0.42
    assert evidence.direction == "BULLISH"

    metadata = dict(
        evidence.metadata
    )

    assert metadata["advances"] == 35
    assert metadata["declines"] == 14
    assert metadata["unchanged"] == 1
    assert metadata["heavyweight_direction"] == "BULLISH"


def test_index_option_chain_preserves_original_pcr_semantics():
    result = adapt_index_option_chain_v1(
        IndexOptionChainSourceV1(
            market="NIFTY",
            observed_at=NOW,
            generated_at=NOW,
            pcr_value=0.30,
            pcr_direction="BULLISH",
            pcr_interpretation="INDEX_LEGACY_LOW_PCR_BULLISH",
            max_pain=22700.0,
        )
    )

    pcr = result.evidence[0]

    assert pcr.feature == "PCR"
    assert pcr.value == 0.30
    assert pcr.direction == "BULLISH"

    assert dict(
        pcr.metadata
    )["source_interpretation"] == (
        "INDEX_LEGACY_LOW_PCR_BULLISH"
    )


def test_index_pcr_adapter_does_not_invent_normalized_direction():
    bullish = adapt_index_option_chain_v1(
        IndexOptionChainSourceV1(
            market="NIFTY",
            observed_at=NOW,
            generated_at=NOW,
            pcr_value=0.30,
            pcr_direction="BULLISH",
            pcr_interpretation="SOURCE_A",
        )
    )

    bearish = adapt_index_option_chain_v1(
        IndexOptionChainSourceV1(
            market="NIFTY",
            observed_at=NOW,
            generated_at=NOW,
            pcr_value=0.30,
            pcr_direction="BEARISH",
            pcr_interpretation="SOURCE_B",
        )
    )

    assert bullish.evidence[0].direction == "BULLISH"
    assert bearish.evidence[0].direction == "BEARISH"


def test_option_chain_preserves_max_pain_support_and_resistance():
    result = adapt_index_option_chain_v1(
        IndexOptionChainSourceV1(
            market="SENSEX",
            observed_at=NOW,
            generated_at=NOW,
            pcr_value=0.90,
            max_pain=72600.0,
            support=72400.0,
            resistance=73000.0,
        )
    )

    values = {
        item.feature:
            item.value
        for item in result.evidence
    }

    assert values["MAX_PAIN"] == 72600.0
    assert values["SUPPORT"] == 72400.0
    assert values["RESISTANCE"] == 73000.0


def test_mcx_unverified_event_is_not_promoted():
    result = adapt_mcx_event_risk_v1(
        McxEventRiskSourceV1(
            market="GOLDM",
            observed_at=NOW,
            generated_at=NOW,
            status="UNVERIFIED",
            freshness="UNKNOWN",
            event_state="UNKNOWN_EVENT_AUTHORITY",
            event_name="SOURCE_EVENT",
            minutes_to_event=15,
            provider_block_entries=False,
            hard_block_eligible=False,
            source_authoritative=False,
        )
    )

    evidence = result.evidence[0]

    assert result.status == "PARTIAL"
    assert evidence.status == "UNVERIFIED"
    assert evidence.source_authoritative is False

    metadata = dict(
        evidence.metadata
    )

    assert metadata["provider_block_entries"] is False
    assert metadata["hard_block_eligible"] is False


def test_every_current_production_registry_descriptor_has_adapter_output():
    expected = {
        item.analyzer_id
        for item
        in DEFAULT_ANALYZER_REGISTRY_V1.production_inputs()
    }

    actual = {
        result.analyzer
        for result
        in production_outputs()
    }

    assert len(expected) == 17
    assert actual == expected


def test_coverage_is_exactly_seventeen_of_seventeen():
    expected = DEFAULT_ANALYZER_REGISTRY_V1.production_inputs()

    actual = {
        result.analyzer
        for result
        in production_outputs()
    }

    assert len(expected) == 17
    assert len(actual) == 17


def test_adapter_coverage_does_not_include_shadow_canonical_engine():
    actual = {
        result.analyzer
        for result
        in production_outputs()
    }

    assert (
        "canonical.technical_intelligence.v1"
        not in actual
    )


def test_all_coverage_outputs_remain_zero_execution_authority():
    for result in production_outputs():
        assert result.execution_authority is False


def test_all_coverage_outputs_are_json_serializable():
    payload = [
        result.to_dict()
        for result
        in production_outputs()
    ]

    json.dumps(
        payload,
        sort_keys=True,
    )


@pytest.mark.parametrize(
    "source,adapter",
    [
        (
            IndexBreadthSourceV1(
                market="CRUDEOILM",
                observed_at=NOW,
                generated_at=NOW,
            ),
            adapt_index_breadth_v1,
        ),

        (
            IndexOptionChainSourceV1(
                market="GOLDM",
                observed_at=NOW,
                generated_at=NOW,
            ),
            adapt_index_option_chain_v1,
        ),

        (
            McxEventRiskSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
            ),
            adapt_mcx_event_risk_v1,
        ),
    ],
)
def test_adapter_market_boundaries_are_enforced(
    source,
    adapter,
):
    with pytest.raises(
        ValueError,
        match="unsupported adapter market",
    ):
        adapter(
            source
        )


def test_unavailable_event_requires_reason():
    with pytest.raises(
        ValueError,
        match="requires missing_reason",
    ):
        adapt_mcx_event_risk_v1(
            McxEventRiskSourceV1(
                market="CRUDEOILM",
                observed_at=NOW,
                generated_at=NOW,
                status="UNAVAILABLE",
                source_authoritative=False,
                missing_reason=None,
            )
        )
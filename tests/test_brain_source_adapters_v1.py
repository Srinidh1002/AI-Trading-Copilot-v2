from __future__ import annotations

from datetime import datetime, timezone
import ast
import json
from pathlib import Path

import pytest

from services.brain.analyzer_registry_v1 import (
    DEFAULT_ANALYZER_REGISTRY_V1,
)
from services.brain.source_adapters_v1 import (
    IndexNewsSourceV1,
    IndexPremarketSourceV1,
    IndexTechnicalSourceV1,
    McxNativeSourceV1,
    adapt_index_news_v1,
    adapt_index_premarket_v1,
    adapt_index_technical_v1,
    adapt_mcx_native_v1,
)


NOW = datetime(
    2026,
    9,
    30,
    7,
    0,
    tzinfo=timezone.utc,
)


def test_index_premarket_emits_six_registered_results():
    source = IndexPremarketSourceV1(
        market="NIFTY",
        observed_at=NOW,
        generated_at=NOW,
        previous_session_date="2026-09-29",
        previous_open=22732.45,
        previous_high=22753.25,
        previous_low=22569.65,
        previous_close=22716.20,
        gap_points=12.0,
        gap_pct=0.05,
        gap_direction="BULLISH",
        global_bias="BULLISH",
        global_score=0.7,
        vix_value=12.4,
        vix_regime="LOW",
        flow_direction="BEARISH",
        fii_cash_net=-9980.22,
        dii_cash_net=6952.71,
        combined_net=-3027.51,
    )

    results = adapt_index_premarket_v1(
        source
    )

    assert [
        item.analyzer
        for item in results
    ] == [
        "index.previous_session.legacy_v1",
        "index.gap.legacy_v1",
        "index.global_risk.legacy_v1",
        "index.india_vix.legacy_v1",
        "index.institutional_flow.legacy_v1",
        "index.event_calendar.legacy_v1",
    ]


def test_index_event_unverified_state_is_preserved_not_promoted():
    source = IndexPremarketSourceV1(
        market="NIFTY",
        observed_at=NOW,
        generated_at=NOW,
        event_status="UNVERIFIED",
        event_source_authoritative=False,
        event_provider_block_entries=False,
        event_hard_block_eligible=False,
        event_threshold_minutes=10,
    )

    result = adapt_index_premarket_v1(
        source
    )[-1]

    evidence = result.evidence[0]

    assert result.status == "PARTIAL"
    assert evidence.status == "UNVERIFIED"
    assert evidence.source_authoritative is False

    metadata = dict(
        evidence.metadata
    )

    assert metadata[
        "provider_block_entries"
    ] is False

    assert metadata[
        "hard_block_eligible"
    ] is False


def test_index_global_unknown_freshness_is_preserved():
    source = IndexPremarketSourceV1(
        market="SENSEX",
        observed_at=NOW,
        generated_at=NOW,
        global_freshness="UNKNOWN",
        global_bias="BEARISH",
        global_score=-0.6,
    )

    result = adapt_index_premarket_v1(
        source
    )[2]

    assert result.evidence[0].freshness == "UNKNOWN"
    assert result.evidence[0].direction == "BEARISH"


def test_index_news_preserves_partial_feed_information():
    source = IndexNewsSourceV1(
        market="NIFTY",
        observed_at=NOW,
        generated_at=NOW,
        status="DEGRADED",
        freshness="FRESH",
        source="LEGACY_NEWS_ENGINE",
        sentiment="BULLISH",
        direction="BULLISH",
        bullish_count=5,
        bearish_count=1,
        headline_count=20,
        feeds_available=2,
        feeds_expected=3,
    )

    result = adapt_index_news_v1(
        source
    )

    assert result.status == "PARTIAL"

    evidence = result.evidence[0]

    assert evidence.status == "DEGRADED"
    assert evidence.value == "BULLISH"

    metadata = dict(
        evidence.metadata
    )

    assert metadata[
        "feeds_available"
    ] == 2

    assert metadata[
        "feeds_expected"
    ] == 3


def test_index_technical_preserves_source_interpretations():
    source = IndexTechnicalSourceV1(
        market="NIFTY",
        observed_at=NOW,
        generated_at=NOW,
        mtf_direction="BULLISH",
        rsi=57.5,
        rsi_direction="BULLISH",
        adx=26.2,
        adx_direction="BULLISH",
        ema_state="EMA20_ABOVE_EMA50",
        ema_direction="BULLISH",
        macd_state="POSITIVE",
        macd_direction="BULLISH",
        bollinger_state="MID_TO_UPPER",
        bollinger_direction="BULLISH",
        regime="TRENDING",
        regime_direction="BULLISH",
    )

    mtf, regime = adapt_index_technical_v1(
        source
    )

    assert mtf.analyzer == "index.mtf.legacy_v1"
    assert regime.analyzer == "index.regime.legacy_v1"

    values = {
        item.feature:
            (
                item.value,
                item.direction,
            )
        for item in mtf.evidence
    }

    assert values[
        "MTF_DIRECTION"
    ] == (
        "BULLISH",
        "BULLISH",
    )

    assert values[
        "RSI"
    ] == (
        57.5,
        "BULLISH",
    )

    assert values[
        "EMA_STATE"
    ] == (
        "EMA20_ABOVE_EMA50",
        "BULLISH",
    )

    assert values[
        "MACD_STATE"
    ] == (
        "POSITIVE",
        "BULLISH",
    )

    assert values[
        "BOLLINGER_STATE"
    ] == (
        "MID_TO_UPPER",
        "BULLISH",
    )


def test_index_technical_does_not_invent_optional_values():
    source = IndexTechnicalSourceV1(
        market="SENSEX",
        observed_at=NOW,
        generated_at=NOW,
        mtf_direction="MIXED",
        rsi=49.0,
        adx=17.0,
        regime="CHOPPY",
    )

    mtf, _ = adapt_index_technical_v1(
        source
    )

    features = {
        item.feature
        for item in mtf.evidence
    }

    assert "EMA_STATE" not in features
    assert "MACD_STATE" not in features
    assert "BOLLINGER_STATE" not in features


def test_mcx_native_emits_five_registered_results():
    source = McxNativeSourceV1(
        market="CRUDEOILM",
        observed_at=NOW,
        generated_at=NOW,
        mtf_direction="BULLISH",
        regime="TREND",
        regime_direction="BULLISH",
        structure="ABOVE_VWAP",
        structure_direction="BULLISH",
        vwap_relation="ABOVE",
        future_ltp=6210.0,
        price_change_pct=0.4,
        oi_change_pct=1.2,
        price_oi_state="LONG_BUILDUP",
        price_oi_direction="BULLISH",
        raw_pcr=0.93,
        stable_pcr=0.96,
        max_pain=6200.0,
        pcr_direction="BULLISH",
        pcr_interpretation="MCX_NATIVE_SOURCE_RULE",
    )

    results = adapt_mcx_native_v1(
        source
    )

    assert [
        item.analyzer
        for item in results
    ] == [
        "mcx.mtf.native_v1",
        "mcx.regime.native_v1",
        "mcx.structure.native_v1",
        "mcx.price_oi.native_v1",
        "mcx.pcr.native_v1",
    ]


def test_mcx_pcr_preserves_raw_value_stable_value_and_source_interpretation():
    source = McxNativeSourceV1(
        market="GOLDM",
        observed_at=NOW,
        generated_at=NOW,
        raw_pcr=0.74,
        stable_pcr=0.77,
        max_pain=115000.0,
        pcr_direction="BEARISH",
        pcr_interpretation="MCX_NATIVE_LOW_PCR_BEARISH",
    )

    result = adapt_mcx_native_v1(
        source
    )[-1]

    evidence = result.evidence[0]

    assert evidence.value == 0.77
    assert evidence.direction == "BEARISH"

    metadata = dict(
        evidence.metadata
    )

    assert metadata[
        "raw_pcr"
    ] == 0.74

    assert metadata[
        "max_pain"
    ] == 115000.0

    assert metadata[
        "source_interpretation"
    ] == "MCX_NATIVE_LOW_PCR_BEARISH"


def test_adapter_does_not_normalize_pcr_direction():
    bullish = McxNativeSourceV1(
        market="NATGASMINI",
        observed_at=NOW,
        generated_at=NOW,
        raw_pcr=0.3,
        stable_pcr=0.3,
        pcr_direction="BULLISH",
        pcr_interpretation="TEST_SOURCE_RULE",
    )

    bearish = McxNativeSourceV1(
        market="NATGASMINI",
        observed_at=NOW,
        generated_at=NOW,
        raw_pcr=0.3,
        stable_pcr=0.3,
        pcr_direction="BEARISH",
        pcr_interpretation="OTHER_SOURCE_RULE",
    )

    assert (
        adapt_mcx_native_v1(
            bullish
        )[-1].evidence[0].direction
        == "BULLISH"
    )

    assert (
        adapt_mcx_native_v1(
            bearish
        )[-1].evidence[0].direction
        == "BEARISH"
    )


def test_unavailable_mcx_price_oi_requires_explicit_reason():
    source = McxNativeSourceV1(
        market="CRUDEOILM",
        observed_at=NOW,
        generated_at=NOW,
        price_oi_status="UNAVAILABLE",
        price_oi_state=None,
        price_oi_missing_reason=None,
    )

    with pytest.raises(
        ValueError,
        match="requires missing_reason",
    ):
        adapt_mcx_native_v1(
            source
        )


def test_unavailable_mcx_price_oi_preserves_reason():
    source = McxNativeSourceV1(
        market="CRUDEOILM",
        observed_at=NOW,
        generated_at=NOW,
        price_oi_status="UNAVAILABLE",
        price_oi_state=None,
        price_oi_direction="UNKNOWN",
        price_oi_missing_reason="INVALID_OBSERVATION",
    )

    result = adapt_mcx_native_v1(
        source
    )[3]

    assert result.status == "UNAVAILABLE"
    assert (
        result.evidence[0].missing_reason
        == "INVALID_OBSERVATION"
    )


@pytest.mark.parametrize(
    "market",
    [
        "BANKNIFTY",
        "USDINR",
    ],
)
def test_index_adapter_rejects_unsupported_market(
    market,
):
    with pytest.raises(
        ValueError,
        match="unsupported adapter market",
    ):
        adapt_index_premarket_v1(
            IndexPremarketSourceV1(
                market=market,
                observed_at=NOW,
                generated_at=NOW,
            )
        )


def test_mcx_adapter_rejects_index_market():
    with pytest.raises(
        ValueError,
        match="unsupported adapter market",
    ):
        adapt_mcx_native_v1(
            McxNativeSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
            )
        )


def test_every_adapter_result_is_zero_execution_authority():
    index_results = adapt_index_premarket_v1(
        IndexPremarketSourceV1(
            market="NIFTY",
            observed_at=NOW,
            generated_at=NOW,
        )
    )

    technical_results = adapt_index_technical_v1(
        IndexTechnicalSourceV1(
            market="NIFTY",
            observed_at=NOW,
            generated_at=NOW,
        )
    )

    mcx_results = adapt_mcx_native_v1(
        McxNativeSourceV1(
            market="GOLDM",
            observed_at=NOW,
            generated_at=NOW,
        )
    )

    for result in (
        *index_results,
        *technical_results,
        *mcx_results,
    ):
        assert result.execution_authority is False


def test_adapter_outputs_only_registered_production_analyzers():
    outputs = (
        *adapt_index_premarket_v1(
            IndexPremarketSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
            )
        ),
        *adapt_index_technical_v1(
            IndexTechnicalSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
            )
        ),
        *adapt_mcx_native_v1(
            McxNativeSourceV1(
                market="CRUDEOILM",
                observed_at=NOW,
                generated_at=NOW,
            )
        ),
    )

    for result in outputs:
        descriptor = DEFAULT_ANALYZER_REGISTRY_V1.get(
            result.analyzer
        )

        assert (
            descriptor.currently_consumed_by_production
            is True
        )

        assert (
            descriptor.runtime_role
            == "PRODUCTION_INPUT"
        )


def test_adapter_payloads_are_json_serializable():
    result = adapt_mcx_native_v1(
        McxNativeSourceV1(
            market="GOLDM",
            observed_at=NOW,
            generated_at=NOW,
            raw_pcr=1.1,
            stable_pcr=1.05,
        )
    )

    json.dumps(
        [
            item.to_dict()
            for item in result
        ],
        sort_keys=True,
    )


def test_adapter_module_has_no_provider_or_broker_imports():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "source_adapters_v1.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )

    forbidden = (
        "fyers",
        "smartapi",
        "requests",
        "yfinance",
        "broker",
        "execution",
        "order",
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

    assert not any(
        token in module
        for module in imports
        for token in forbidden
    )


def test_adapters_do_not_expose_trade_action_or_execution_methods():
    from services.brain import source_adapters_v1

    forbidden_names = {
        "buy_call",
        "buy_put",
        "place_order",
        "submit_order",
        "execute",
        "send_order",
        "increment_certification",
    }

    actual = {
        name.lower()
        for name in dir(
            source_adapters_v1
        )
    }

    assert not (
        forbidden_names
        & actual
    )


def test_canonical_shadow_analyzer_is_not_emitted_by_source_adapters():
    emitted = {
        result.analyzer
        for result in (
            *adapt_index_technical_v1(
                IndexTechnicalSourceV1(
                    market="NIFTY",
                    observed_at=NOW,
                    generated_at=NOW,
                )
            ),
            *adapt_mcx_native_v1(
                McxNativeSourceV1(
                    market="GOLDM",
                    observed_at=NOW,
                    generated_at=NOW,
                )
            ),
        )
    }

    assert (
        "canonical.technical_intelligence.v1"
        not in emitted
    )
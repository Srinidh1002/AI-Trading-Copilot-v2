"""Focused deterministic aggregation coverage for P5-10H1."""
from datetime import datetime, timezone

import pytest

from services.contracts.broader_market_regime_component_result_v1 import BroaderMarketRegimeComponentResultV1
from services.contracts.market_regime_input_v1 import MarketRegimeInputV1
from services.contracts.market_regime_policy_v1 import (
    DEFAULT_MARKET_REGIME_POLICY,
    MarketRegimePolicyV1,
)
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.technical_regime_component_result_v1 import TechnicalRegimeComponentResultV1
from services.market_regime.aggregate import aggregate_market_regime


TS = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)


def _session(analysis_allowed=True, entries_allowed=True):
    return MarketSessionValidationV1(
        validation_id="session", evaluated_at=TS, market_timestamp=TS, symbol="NIFTY", exchange="NSE",
        timezone="UTC", trading_date=TS.date(), session_state="REGULAR", session_phase="REGULAR_TRADING",
        trading_day_status="TRADING_DAY", analysis_allowed=analysis_allowed,
        paper_execution_allowed=entries_allowed,
    )


def _technical(direction="POSITIVE", strength=0.9, confidence=0.9):
    return TechnicalRegimeComponentResultV1(
        "technical", TS, "NIFTY", "NSE", None, "READY", direction, "UPTREND", "NORMAL",
        strength, confidence, "CONFIRMING", 1, 0,
    )


def _broader(
    direction="POSITIVE",
    strength=1.0,
    confidence=1.0,
    confirmation="CONFIRMING",
):
    return BroaderMarketRegimeComponentResultV1(
        "broader",
        TS,
        "NIFTY",
        "NSE",
        None,
        "READY",
        direction,
        "FLAT",
        "UNAVAILABLE",
        "NORMAL",
        strength,
        confidence,
        confirmation,
        1,
        0,
    )


def _input(technical="DEFAULT", session=None):
    return MarketRegimeInputV1(
        "input-1", TS, "NIFTY", "NSE", market_session_validation=session or _session(),
        technical_regime_component=_technical() if technical == "DEFAULT" else technical,
    )


def test_strong_bullish_is_deterministic_and_preserves_provenance():
    result = aggregate_market_regime(_input())
    assert result.primary_regime == "STRONG_BULLISH"
    assert result.market_regime_result_id == "market-regime:input-1"
    assert result.created_at == TS
    assert result.to_dict() == aggregate_market_regime(_input()).to_dict()
    assert result.technical_regime_component is not None
    assert result.execution_mode == "PAPER" and result.live_execution_eligible is False


def test_required_failure_and_analysis_disallowed_fail_closed():
    failed = aggregate_market_regime(_input(technical=None))
    blocked = aggregate_market_regime(_input(session=_session(False, False)))
    assert failed.primary_regime == blocked.primary_regime == "BLOCKED"
    assert failed.entry_suitability == blocked.entry_suitability == "BLOCKED"


def test_non_unit_outer_weights_remain_supported():
    policy = MarketRegimePolicyV1(technical_weight=2, broader_market_weight=1, external_context_weight=1)
    result = aggregate_market_regime(_input(), policy)
    assert result.primary_regime == "STRONG_BULLISH"
    assert result.regime_strength == 0.9



def test_optional_component_unavailability_warns_penalizes_but_does_not_make_suitable_impossible():
    result = aggregate_market_regime(
        _input()
    )

    assert result.context_status == "READY_WITH_WARNINGS"

    assert result.warnings == (
        "OPTIONAL_BROADER_MARKET_UNUSABLE",
        "OPTIONAL_EXTERNAL_CONTEXT_UNUSABLE",
    )

    # Technical confidence starts at 0.90.
    #
    # Missing optional evidence keeps its dedicated -0.05
    # confidence penalty. The generated OPTIONAL_*_UNUSABLE
    # warning is retained for observability but must not charge
    # the same absence a second time through warning_penalty.
    #
    # The resulting 0.85 exceeds the unchanged 0.70
    # suitable-confidence threshold.
    assert result.confidence == pytest.approx(0.85)

    assert result.entry_suitability == "SUITABLE"
    assert result.analysis_allowed is True
    assert result.new_entries_allowed is True

    assert "MISSING_OPTIONAL" in result.metadata[
        "applied_penalties"
    ]

    assert "WARNING" not in result.metadata[
        "applied_penalties"
    ]


def test_optional_component_unavailability_allows_bearish_suitable_regime_after_same_penalties():
    result = aggregate_market_regime(
        _input(
            technical=_technical(
                direction="NEGATIVE",
                strength=0.9,
                confidence=0.9,
            )
        )
    )

    assert result.primary_regime == "STRONG_BEARISH"
    assert result.context_status == "READY_WITH_WARNINGS"
    assert result.confidence == pytest.approx(0.85)
    assert result.entry_suitability == "SUITABLE"

    assert result.warnings == (
        "OPTIONAL_BROADER_MARKET_UNUSABLE",
        "OPTIONAL_EXTERNAL_CONTEXT_UNUSABLE",
    )


def test_realizable_technical_ceiling_with_perfect_broader_market_and_missing_external_can_be_suitable():
    from dataclasses import replace

    base = _input()

    technical = _technical(
        direction="POSITIVE",
        strength=0.70,
        confidence=0.70,
    )

    broader = _broader(
        direction="POSITIVE",
        strength=1.0,
        confidence=1.0,
        confirmation="CONFIRMING",
    )

    market_input = replace(
        base,
        technical_regime_component=technical,
        broader_market_regime_component=broader,
        external_context_regime_component=None,
        warnings=(),
        blockers=(),
    )

    result = aggregate_market_regime(
        market_input
    )

    expected_raw = (
        (
            0.60 * 0.70
            + 0.25 * 1.0
        )
        /
        (
            0.60
            + 0.25
        )
    )

    expected = (
        expected_raw
        - DEFAULT_MARKET_REGIME_POLICY.missing_optional_component_penalty
    )

    assert expected > DEFAULT_MARKET_REGIME_POLICY.suitable_confidence_threshold
    assert result.confidence == pytest.approx(expected)

    assert result.context_status == "READY_WITH_WARNINGS"
    assert result.entry_suitability == "SUITABLE"
    assert result.new_entries_allowed is True

    assert result.warnings == (
        "OPTIONAL_EXTERNAL_CONTEXT_UNUSABLE",
    )

    assert "MISSING_OPTIONAL" in result.metadata[
        "applied_penalties"
    ]

    assert "WARNING" not in result.metadata[
        "applied_penalties"
    ]



def test_non_optional_warning_still_prevents_suitable():
    from dataclasses import replace

    market_input = replace(
        _input(),
        warnings=(
            "COMPONENT_TIMESTAMP_SKEW",
        ),
    )

    result = aggregate_market_regime(
        market_input
    )

    assert result.context_status == "READY_WITH_WARNINGS"

    assert (
        "OPTIONAL_BROADER_MARKET_UNUSABLE"
        in result.warnings
    )

    assert (
        "OPTIONAL_EXTERNAL_CONTEXT_UNUSABLE"
        in result.warnings
    )

    assert (
        "COMPONENT_TIMESTAMP_SKEW"
        in result.warnings
    )

    assert result.entry_suitability == "CAUTION"


def test_optional_timeframe_warning_pair_remains_visible_without_vetoing_suitability():
    from dataclasses import replace

    result = aggregate_market_regime(
        replace(
            _input(),
            warnings=(
                "OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",
                "TECHNICAL_TIMEFRAME_UNAVAILABLE_1D",
            ),
        )
    )

    assert result.entry_suitability == "SUITABLE"
    assert result.confidence == pytest.approx(0.85)
    assert "MISSING_OPTIONAL" in result.metadata["applied_penalties"]
    assert "WARNING" not in result.metadata["applied_penalties"]
    assert "OPTIONAL_TIMEFRAME_UNAVAILABLE_1D" in result.warnings
    assert "TECHNICAL_TIMEFRAME_UNAVAILABLE_1D" in result.warnings


@pytest.mark.parametrize(
    ("warnings", "expected_confidence"),
    (
        (("OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",), 0.80),
        (("TECHNICAL_TIMEFRAME_UNAVAILABLE_1D",), 0.80),
        (
            (
                "OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",
                "TECHNICAL_TIMEFRAME_UNAVAILABLE_1H",
            ),
            0.80,
        ),
        (
            (
                "OPTIONAL_TIMEFRAME_UNAVAILABLE_",
                "TECHNICAL_TIMEFRAME_UNAVAILABLE_",
            ),
            0.80,
        ),
        (
            (
                "OPTIONAL_TIMEFRAME_UNAVAILABLE_UNEXPLAINED",
                "TECHNICAL_TIMEFRAME_UNAVAILABLE_UNEXPLAINED",
            ),
            0.80,
        ),
    ),
)
def test_unpaired_or_malformed_optional_timeframe_warnings_retain_penalty_and_veto(
    warnings,
    expected_confidence,
):
    from dataclasses import replace

    result = aggregate_market_regime(replace(_input(), warnings=warnings))

    assert result.confidence == pytest.approx(expected_confidence)
    assert result.entry_suitability == "CAUTION"
    assert "WARNING" in result.metadata["applied_penalties"]
    assert set(warnings).issubset(result.warnings)


def test_rising_volatility_remains_a_suitability_warning_with_optional_timeframe_pair():
    from dataclasses import replace

    result = aggregate_market_regime(
        replace(
            _input(),
            warnings=(
                "OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",
                "TECHNICAL_TIMEFRAME_UNAVAILABLE_1D",
                "NORMALIZED VOLATILITY IS RISING",
            ),
        )
    )

    assert result.confidence == pytest.approx(0.80)
    assert result.entry_suitability == "CAUTION"
    assert "WARNING" in result.metadata["applied_penalties"]


def test_session_cutoff_remains_not_suitable_with_optional_timeframe_warning_pair():
    from dataclasses import replace

    result = aggregate_market_regime(
        replace(
            _input(session=_session(True, False)),
            warnings=(
                "OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",
                "TECHNICAL_TIMEFRAME_UNAVAILABLE_1D",
            ),
        )
    )

    assert result.entry_suitability == "NOT_SUITABLE"
    assert result.new_entries_allowed is False


def test_required_failure_remains_fail_closed_after_optional_warning_fix():
    result = aggregate_market_regime(
        _input(
            technical=None,
        )
    )

    assert result.primary_regime == "BLOCKED"
    assert result.context_status == "BLOCKED"
    assert result.entry_suitability == "BLOCKED"
    assert result.new_entries_allowed is False

    assert (
        "REQUIRED_TECHNICAL_UNUSABLE"
        in result.blockers
    )

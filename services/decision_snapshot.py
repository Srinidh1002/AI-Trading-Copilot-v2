"""
Decision snapshot builder.

Freezes selected market intelligence at the moment a paper trade
is opened so future historical-performance analysis can compare
trade outcomes with the conditions that existed at entry.

Read-only.
Does not place orders.
Does not modify the live trading decision.
"""

from copy import deepcopy


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def build_decision_snapshot(
    pipeline_result,
):
    """
    Build a compact, immutable historical-learning snapshot.

    The snapshot records decision-time context only.
    It does not influence the current live decision.
    """

    if not isinstance(
        pipeline_result,
        dict,
    ):
        raise ValueError(
            "pipeline_result must be a dictionary."
        )

    market_analysis = _safe_dict(
        pipeline_result.get(
            "market_analysis"
        )
    )

    strategy = _safe_dict(
        market_analysis.get(
            "strategy"
        )
    )

    regime = _safe_dict(
        market_analysis.get(
            "regime"
        )
    )

    timeframe = _safe_dict(
        market_analysis.get(
            "timeframe"
        )
    )

    technical = _safe_dict(
        market_analysis.get(
            "technical"
        )
    )

    candlestick = _safe_dict(
        market_analysis.get(
            "candlestick"
        )
    )

    chart = _safe_dict(
        market_analysis.get(
            "chart"
        )
    )

    volume = _safe_dict(
        market_analysis.get(
            "volume"
        )
    )

    regime_evidence = _safe_dict(
        market_analysis.get(
            "regime_aware_evidence"
        )
    )

    setup_trigger = _safe_dict(
        pipeline_result.get(
            "setup_trigger"
        )
    )

    contract = _safe_dict(
        pipeline_result.get(
            "contract"
        )
    )

    snapshot = {
        "decision": (
            pipeline_result.get(
                "decision"
            )
        ),
        "market_decision": (
            pipeline_result.get(
                "market_decision"
            )
        ),
        "direction": (
            pipeline_result.get(
                "direction"
            )
        ),

        "strategy": (
            strategy.get(
                "strategy"
            )
        ),
        "strategy_decision": (
            strategy.get(
                "decision"
            )
        ),
        "strategy_confidence": (
            strategy.get(
                "direction_confidence",
                strategy.get(
                    "confidence"
                ),
            )
        ),
        "strategy_direction_confidence": (
            strategy.get(
                "direction_confidence",
                strategy.get(
                    "confidence"
                ),
            )
        ),
        "strategy_evidence_strength_score": (
            strategy.get(
                "evidence_strength_score"
            )
        ),
        "strategy_evidence_strength_label": (
            strategy.get(
                "evidence_strength_label"
            )
        ),
        "risk_flags": deepcopy(
            strategy.get(
                "risk_flags",
                [],
            )
            or []
        ),

        "market_regime": (
            regime.get(
                "primary_regime"
            )
        ),
        "regime_trend": (
            regime.get(
                "trend"
            )
        ),
        "regime_confidence": (
            regime.get(
                "confidence"
            )
        ),

        "timeframe_trend": (
            timeframe.get(
                "overall_trend"
            )
        ),
        "timeframe_alignment": (
            timeframe.get(
                "alignment"
            )
        ),
        "timeframe_confidence": (
            timeframe.get(
                "confidence"
            )
        ),

        "technical_trend": (
            technical.get(
                "trend"
            )
        ),
        "technical_score": (
            technical.get(
                "score"
            )
        ),
        "technical_confidence": (
            technical.get(
                "confidence"
            )
        ),

        "candlestick_signal": (
            candlestick.get(
                "signal"
            )
        ),
        "candlestick_patterns": deepcopy(
            candlestick.get(
                "patterns",
                [],
            )
            or []
        ),
        "support": (
            candlestick.get(
                "support"
            )
        ),
        "resistance": (
            candlestick.get(
                "resistance"
            )
        ),

        "chart_signal": (
            chart.get(
                "signal"
            )
        ),
        "chart_patterns": deepcopy(
            chart.get(
                "patterns",
                [],
            )
            or []
        ),

        "volume_bias": (
            volume.get(
                "bias"
            )
        ),
        "relative_volume": (
            volume.get(
                "relative_volume"
            )
        ),
        "volume_spike": (
            volume.get(
                "volume_spike"
            )
        ),
        "volume_signals": deepcopy(
            volume.get(
                "signals",
                [],
            )
            or []
        ),

        "contextual_bias": (
            regime_evidence.get(
                "contextual_bias"
            )
        ),
        "relevant_signals": deepcopy(
            regime_evidence.get(
                "relevant_signals",
                [],
            )
            or []
        ),
        "confirmations": deepcopy(
            regime_evidence.get(
                "confirmations",
                [],
            )
            or []
        ),
        "warnings": deepcopy(
            regime_evidence.get(
                "warnings",
                [],
            )
            or []
        ),

        "setup_status": (
            setup_trigger.get(
                "status"
            )
        ),
        "setup_direction": (
            setup_trigger.get(
                "direction"
            )
        ),
        "trigger_type": (
            setup_trigger.get(
                "trigger_type"
            )
        ),
        "trigger_price": (
            setup_trigger.get(
                "trigger_price"
            )
        ),

        "option_symbol": (
            contract.get(
                "symbol"
            )
        ),
        "option_type": (
            contract.get(
                "option_type"
            )
        ),
        "strike": (
            contract.get(
                "strike"
            )
        ),
        "expiry": (
            contract.get(
                "expiry"
            )
        ),
    }

    return deepcopy(
        snapshot
    )
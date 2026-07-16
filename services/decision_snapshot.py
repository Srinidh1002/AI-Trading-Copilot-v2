"""
Decision snapshot builder.

Freezes selected market intelligence at the moment a paper trade
is opened so future historical-performance analysis can compare
trade outcomes with the conditions that existed at entry.

Read-only.
Does not place orders.
Does not modify the live trading decision.
"""

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from services.indicator_snapshot import IndicatorSnapshot

INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


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

    trade_candidate_research = _safe_dict(
        pipeline_result.get(
            "trade_candidate_research"
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
        "formation_status": (
            setup_trigger.get(
                "formation_status"
            )
        ),
        "setup_maturity_score": (
            setup_trigger.get(
                "setup_maturity_score"
            )
        ),
        "distance_to_trigger": (
            setup_trigger.get(
                "distance_to_trigger"
            )
        ),
        "distance_to_trigger_percent": (
            setup_trigger.get(
                "distance_to_trigger_percent"
            )
        ),
        "trade_candidate_score": (
            trade_candidate_research.get(
                "trade_candidate_score"
            )
        ),
        "candidate_label": (
            trade_candidate_research.get(
                "candidate_label"
            )
        ),
        "candidate_passed_conditions": deepcopy(
            trade_candidate_research.get(
                "passed_conditions",
                [],
            )
            or []
        ),
        "candidate_missing_conditions": deepcopy(
            trade_candidate_research.get(
                "missing_conditions",
                [],
            )
            or []
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


def _json_default(value):
    """Serialize timestamp-like values without changing the source result."""

    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()

    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable."
    )


def build_live_decision_snapshot(
    pipeline_result,
    *,
    underlying,
    spot_price,
    paper_trading_result=None,
    timestamp=None,
):
    """Build the persisted, observational snapshot for one pipeline run."""

    if not isinstance(pipeline_result, dict):
        raise ValueError("pipeline_result must be a dictionary.")

    timestamp = (
        timestamp
        if timestamp is not None
        else datetime.now(INDIA_TIMEZONE)
    )

    base_snapshot = build_decision_snapshot(pipeline_result)

    market_analysis = _safe_dict(
        pipeline_result.get("market_analysis")
    )

    regime = _safe_dict(
        market_analysis.get("regime")
    )

    session = _safe_dict(
        pipeline_result.get("session_status")
        or pipeline_result.get("market_session")
    )

    completed_candle = _safe_dict(
        pipeline_result.get("completed_candle")
    )

    paper_result = _safe_dict(
        paper_trading_result
    )

    #
    # Read-only indicator snapshot
    #
    try:
        indicator_snapshot = (
            IndicatorSnapshot()
            .build(pipeline_result)
    )
    except Exception as e:
            indicator_snapshot = {
            "error": str(e),
    }

    return {
        "timestamp": timestamp.isoformat(),
        "underlying": underlying,
        "spot_price": spot_price,
        "market_session": deepcopy(session),

        "candle_timestamp": session.get(
            "candle_timestamp"
        ),
        "candle_age_minutes": session.get(
            "candle_age_minutes"
        ),
        "candle_fresh": session.get(
            "candle_fresh"
        ),

        "decision": pipeline_result.get(
            "decision"
        ),
        "direction": pipeline_result.get(
            "direction"
        ),

        "confidence": base_snapshot.get(
            "strategy_confidence"
        ),

        "evidence_strength": base_snapshot.get(
            "strategy_evidence_strength_score"
        ),

        "evidence_strength_label": base_snapshot.get(
            "strategy_evidence_strength_label"
        ),

        "strategy": base_snapshot.get(
            "strategy"
        ),

        "primary_regime": regime.get(
            "primary_regime"
        ),

        "trend": regime.get(
            "trend"
        ),

        "volatility": regime.get(
            "volatility"
        ),

        "regime_confidence": regime.get(
            "confidence"
        ),

        "support": base_snapshot.get(
            "support"
        ),

        "resistance": base_snapshot.get(
            "resistance"
        ),

        "volume_bias": base_snapshot.get(
            "volume_bias"
        ),

        "relative_volume": base_snapshot.get(
            "relative_volume"
        ),

        "volume_spike": base_snapshot.get(
            "volume_spike"
        ),

        "setup_status": base_snapshot.get(
            "setup_status"
        ),

        "trigger_type": base_snapshot.get(
            "trigger_type"
        ),

        "risk_flags": deepcopy(
            base_snapshot.get(
                "risk_flags",
                [],
            )
        ),

        "relevant_signals": deepcopy(
            base_snapshot.get(
                "relevant_signals",
                [],
            )
        ),

        "paper_trade_status": paper_result.get(
            "status"
        ),

        "selected_option_contract": deepcopy(
            _safe_dict(
                pipeline_result.get(
                    "contract"
                )
            )
        ),

        "completed_candle": deepcopy(
            completed_candle
        ),

        #
        # NEW
        #
        "chart_patterns": deepcopy(
    _safe_dict(
        pipeline_result.get(
            "setup_trigger"
        )
    ).get(
        "chart_patterns",
        [],
    )
),

"formation_status": _safe_dict(
    pipeline_result.get(
        "setup_trigger"
    )
).get(
    "formation_status"
),

"setup_maturity_score": _safe_dict(
    pipeline_result.get(
        "setup_trigger"
    )
).get(
    "setup_maturity_score"
),

"distance_to_trigger": _safe_dict(
    pipeline_result.get(
        "setup_trigger"
    )
).get(
    "distance_to_trigger"
),

"distance_to_trigger_percent": _safe_dict(
    pipeline_result.get(
        "setup_trigger"
    )
).get(
    "distance_to_trigger_percent"
),
        "indicator_snapshot": deepcopy(
            indicator_snapshot
        ),
    }


def save_live_decision_snapshot(
    snapshot,
    *,
    base_path="data/decision_snapshots",
):
    """Persist a snapshot and return its outcome without raising.

    Snapshot persistence is diagnostic only. Any filesystem or serialization
    failure is deliberately contained so it can never affect a live decision.
    """

    try:
        if not isinstance(snapshot, dict):
            raise ValueError("snapshot must be a dictionary.")

        timestamp = datetime.fromisoformat(snapshot["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=INDIA_TIMEZONE)
        else:
            timestamp = timestamp.astimezone(INDIA_TIMEZONE)

        directory = Path(base_path) / timestamp.strftime("%Y-%m-%d")
        destination = directory / f"{timestamp:%H-%M}.json"
        temporary = destination.with_suffix(".json.tmp")
        directory.mkdir(parents=True, exist_ok=True)

        try:
            with temporary.open("w", encoding="utf-8") as file:
                json.dump(
                    snapshot,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    default=_json_default,
                )
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, destination)
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise

        return {
            "saved": True,
            "path": str(destination),
            "error": None,
        }

    except Exception as exc:
        return {
            "saved": False,
            "path": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def persist_live_decision_snapshot(
    pipeline_result,
    *,
    underlying,
    spot_price,
    paper_trading_result=None,
    base_path="data/decision_snapshots",
    timestamp=None,
):
    """Build and save a diagnostic snapshot without propagating failures."""

    try:
        snapshot = build_live_decision_snapshot(
            pipeline_result,
            underlying=underlying,
            spot_price=spot_price,
            paper_trading_result=paper_trading_result,
            timestamp=timestamp,
        )
    except Exception as exc:
        return {
            "saved": False,
            "path": None,
            "error": f"{type(exc).__name__}: {exc}",
        }

    return save_live_decision_snapshot(
        snapshot,
        base_path=base_path,
    )

"""Canonical, pure, paper-only technical intelligence primitives."""
from .indicators import (calculate_adx, calculate_atr, calculate_bollinger_bands, calculate_ema, calculate_macd, calculate_rsi, calculate_sma, calculate_true_range, calculate_volume_average, calculate_vwap)
from .trend import evaluate_trend_intelligence
from .momentum import evaluate_momentum_intelligence
from .volatility import evaluate_volatility_intelligence
from .levels import evaluate_level_intelligence
from .patterns import evaluate_pattern_intelligence
from .timeframe_analysis import analyze_timeframe_technical_evidence
from .aggregation import aggregate_technical_intelligence
from .pipeline import build_canonical_technical_intelligence

__all__ = ["DEFAULT_TECHNICAL_INTELLIGENCE_POLICY", "calculate_sma", "calculate_ema", "calculate_rsi", "calculate_macd", "calculate_true_range", "calculate_atr", "calculate_adx", "calculate_bollinger_bands", "calculate_vwap", "calculate_volume_average", "evaluate_trend_intelligence", "evaluate_momentum_intelligence", "evaluate_volatility_intelligence", "evaluate_level_intelligence", "evaluate_pattern_intelligence", "analyze_timeframe_technical_evidence", "aggregate_technical_intelligence", "build_canonical_technical_intelligence"]

def __getattr__(name: str):
    if name == "DEFAULT_TECHNICAL_INTELLIGENCE_POLICY":
        from services.contracts.technical_intelligence_policy_v1 import DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
        return DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
    raise AttributeError(name)

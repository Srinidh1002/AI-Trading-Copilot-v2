"""Deterministic P5-4C behavioral fixtures."""
from .market_series import CANONICAL_IDENTITIES, REQUIRED_TIMEFRAMES, bullish_series, bearish_series, flat_series, breakout_series, breakdown_series, insufficient_history_series, incomplete_series
from .timeframe_evidence import timeframe_evidence
from .multi_timeframe import snapshot, quality_result
from .technical_evidence import technical_evidence, technical_bundle
from .policies import default_policy, policy_variant

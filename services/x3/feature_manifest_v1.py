"""Provisional X3 manifest: X9 owns formal analyzer registration."""

from __future__ import annotations

from services.x3.contracts_v1 import FAMILIES

X3_FEATURE_MANIFEST_V1 = {
    "schema_version": "X3_FEATURE_MANIFEST_V1",
    "source_families": {
        "TREND": "PRICE_OHLC",
        "MOMENTUM": "PRICE_OHLC",
        "EXHAUSTION": "PRICE_OHLC",
        "VOLATILITY": "PRICE_OHLC",
        "VOLUME_PARTICIPATION": "OHLC_VOLUME",
        "STRUCTURE": "PRICE_OHLC",
        "PATTERN": "PRICE_OHLC",
    },
    "family_ids": FAMILIES,
    "deduplication_unit": "ONE_RESULT_PER_FAMILY",
    "formal_registry_version": "DEFERRED_TO_X9",
    "market_hypothesis": "DEFERRED_TO_X10",
    "data_only": True,
    "order_capability_allowed": False,
    "automatic_fallback_allowed": False,
    "execution_authority": False,
    "risk_authority": False,
    "position_authority": False,
    "certification_authority": False,
}

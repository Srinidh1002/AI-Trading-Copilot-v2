"""Exact structural usability vocabulary for canonical warning-bearing evidence."""
from __future__ import annotations
from services.contracts.technical_intelligence_result_v1 import (
    is_usable_technical_status as _is_usable_technical_status,
)


def is_usable_technical_status(status: object) -> bool:
    return _is_usable_technical_status(status)


def is_usable_option_intelligence_status(status: object) -> bool:
    return status in {"READY", "READY_WITH_WARNINGS"}


def is_usable_option_ranking_status(status: object) -> bool:
    return status in {"RANKED", "RANKED_WITH_WARNINGS"}


def is_usable_regime_status(status: object) -> bool:
    # Regime warning states require the caller to inspect entry suitability.
    # The live candidate composer has no broader/external context to establish
    # that warning state as entry-ready, so only exact READY is usable here.
    return status == "READY"

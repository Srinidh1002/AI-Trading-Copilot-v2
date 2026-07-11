"""Agent adapter for option-chain analysis."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from models.option_state import OptionState
from services.option_analyzer import analyse_options as analyse_option_chain


class OptionAgent:
    """Convert option-chain data into an application-level option state."""

    def analyse(self, option_chain: Mapping[str, Any]) -> OptionState:
        """Analyse option-chain data and return its key trading levels."""

        analysis = analyse_option_chain(option_chain)
        return OptionState(
            pcr=analysis["pcr"],
            support=analysis["support"],
            resistance=analysis["resistance"],
            max_pain=analysis["max_pain"],
            score=analysis["score"],
            confidence=analysis["confidence"],
            reasons=analysis["reasons"],
        )

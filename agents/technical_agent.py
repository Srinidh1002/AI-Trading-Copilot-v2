"""Agent adapter for technical OHLCV analysis."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from services.technical_analyzer import TechnicalIndicators, analyse_technical


@dataclass
class TechnicalState:
    """Technical analysis state exposed to the application layer."""

    trend: str
    score: int
    confidence: int
    reasons: list[str]
    indicators: TechnicalIndicators


class TechnicalAgent:
    """Convert raw OHLCV data into a technical analysis state."""

    def analyse(self, df: pd.DataFrame) -> TechnicalState:
        """Analyse an OHLCV data frame and return its technical state."""

        analysis = analyse_technical(df)
        return TechnicalState(
            trend=analysis["trend"],
            score=analysis["score"],
            confidence=analysis["confidence"],
            reasons=analysis["reasons"],
            indicators=analysis["indicators"],
        )

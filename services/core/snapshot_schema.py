"""
Snapshot Schema

Defines the Market Snapshot shared across the entire trading system.
"""

from dataclasses import dataclass
from typing import Any
import pandas as pd


@dataclass(slots=True)
class Snapshot:

    # ------------------------
    # Raw Data
    # ------------------------

    history: pd.DataFrame

    # ------------------------
    # Latest Candle
    # ------------------------

    ltp: float
    open: float
    high: float
    low: float
    close: float
    volume: int

    candle_time: str

    # ------------------------
    # Market Status
    # ------------------------

    market_status: str
    refresh_time: str

    # ------------------------
    # Technical Indicators
    # ------------------------

    indicators: dict[str, Any]

    # ------------------------
    # Analysis Results
    # ------------------------

    analysis: dict[str, Any]

    # ------------------------
    # Decision
    # ------------------------

    decision: dict[str, Any]

    # ------------------------
    # Risk
    # ------------------------

    risk: dict[str, Any]
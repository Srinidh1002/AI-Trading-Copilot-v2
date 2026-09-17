"""
Option-chain intelligence scoring with graceful degradation for partial chains.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from collections.abc import Mapping, Sequence
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_option_chain(symbol: str, expiry: Optional[str] = None) -> Dict:
    """
    Get option chain data for a symbol.
    
    Args:
        symbol: Market symbol (NIFTY, SENSEX)
        expiry: Optional expiry date
        
    Returns:
        Dict with option chain data
    """
    return {
        "symbol": symbol,
        "expiry": expiry,
        "pcr": 1.0,
        "max_pain": 0,
        "iv": 20.0,
        "oi_concentration": 0.0,
        "support": 0,
        "resistance": 0,
        "available": False,
        "calls": [],
        "puts": [],
    }


@dataclass(frozen=True, slots=True)
class OptionScoreConfig:
    pcr_weight: float = 15.0
    oi_weight: float = 20.0
    writing_weight: float = 15.0
    max_pain_weight: float = 10.0
    premium_weight: float = 10.0
    iv_weight: float = 10.0
    greeks_weight: float = 10.0
    liquidity_weight: float = 10.0
    bullish_pcr: float = 1.05
    bearish_pcr: float = 0.80


class OptionScoreEngine:
    """Option score engine with graceful degradation."""
    
    def __init__(self, config: Optional[OptionScoreConfig] = None):
        self.config = config or OptionScoreConfig()
        self.logger = logging.getLogger(__name__)
    
    def score(self, chain_data: Dict) -> Dict:
        """Score option chain data."""
        if not chain_data or not chain_data.get("available", True):
            return {
                "score": 50,
                "confidence": 30,
                "reasons": ["Option chain data not available"],
                "pcr": 1.0,
                "support": 0,
                "resistance": 0,
                "max_pain": 0,
                "available": False
            }
        
        pcr = chain_data.get("pcr", 1.0)
        support = chain_data.get("support", 0)
        resistance = chain_data.get("resistance", 0)
        max_pain = chain_data.get("max_pain", 0)
        
        score = 50
        reasons = []
        
        if pcr > self.config.bullish_pcr:
            score += 20
            reasons.append(f"PCR bullish: {pcr:.2f}")
        elif pcr < self.config.bearish_pcr:
            score -= 20
            reasons.append(f"PCR bearish: {pcr:.2f}")
        else:
            reasons.append(f"PCR neutral: {pcr:.2f}")
        
        if support > 0:
            score += 10
            reasons.append(f"Support at {support}")
        if resistance > 0:
            score -= 10
            reasons.append(f"Resistance at {resistance}")
        
        if max_pain > 0:
            score += 5
            reasons.append(f"Max pain at {max_pain}")
        
        score = max(0, min(100, score))
        
        return {
            "score": score,
            "confidence": score,
            "reasons": reasons,
            "pcr": pcr,
            "support": support,
            "resistance": resistance,
            "max_pain": max_pain,
            "available": True
        }

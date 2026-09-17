"""
Option AI - Options intelligence scoring.
"""

from typing import Dict

from services.analysis.option_chain import get_option_chain, OptionScoreEngine
import logging

logger = logging.getLogger(__name__)


def option_score(chain_data: Dict) -> Dict:
    """
    Score option chain data.
    
    Args:
        chain_data: Option chain data
        
    Returns:
        Dict with score and reasons
    """
    engine = OptionScoreEngine()
    result = engine.score(chain_data)
    
    return {
        "score": result.get("score", 50),
        "confidence": result.get("confidence", 50),
        "reasons": result.get("reasons", ["No option data"]),
        "pcr": result.get("pcr", 1.0),
        "support": result.get("support", 0),
        "resistance": result.get("resistance", 0),
        "max_pain": result.get("max_pain", 0),
    }

"""
Full Market Comparison Engine - PDF Section 13
NIFTY vs SENSEX competition with multi-factor scoring.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass
class MarketScore:
    """Score for a single market."""
    market: str
    technical_trend: float = 0.0
    momentum: float = 0.0
    option_structure: float = 0.0
    liquidity: float = 0.0
    global_alignment: float = 0.0
    volatility_quality: float = 0.0
    news_alignment: float = 0.0
    risk_reward: float = 0.0
    composite_score: float = 0.0
    factors: Dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    
    def calculate_composite(self) -> float:
        """Calculate weighted composite score."""
        weights = {
            "technical_trend": 0.18,
            "momentum": 0.12,
            "option_structure": 0.15,
            "liquidity": 0.10,
            "global_alignment": 0.10,
            "volatility_quality": 0.10,
            "news_alignment": 0.10,
            "risk_reward": 0.15,
        }
        
        self.composite_score = (
            self.technical_trend * weights["technical_trend"] +
            self.momentum * weights["momentum"] +
            self.option_structure * weights["option_structure"] +
            self.liquidity * weights["liquidity"] +
            self.global_alignment * weights["global_alignment"] +
            self.volatility_quality * weights["volatility_quality"] +
            self.news_alignment * weights["news_alignment"] +
            self.risk_reward * weights["risk_reward"]
        )
        
        return self.composite_score


@dataclass
class MarketComparisonResult:
    """Result of market comparison."""
    nifty_score: MarketScore
    sensex_score: MarketScore
    winner: Optional[str] = None
    winner_score: float = 0.0
    loser_score: float = 0.0
    difference: float = 0.0
    confidence: float = 0.0
    decision: str = "NO_TRADE"
    reasons: list[str] = field(default_factory=list)
    nifty_composite: float = 0.0
    sensex_composite: float = 0.0


def compare_markets_full(nifty_data: Dict, sensex_data: Dict) -> MarketComparisonResult:
    """
    Full market comparison with 8-factor scoring.
    PDF Section 13 - Competition between NIFTY and SENSEX.
    """
    # Score each market
    nifty_score = _score_market("NIFTY", nifty_data)
    sensex_score = _score_market("SENSEX", sensex_data)
    
    nifty_composite = nifty_score.calculate_composite()
    sensex_composite = sensex_score.calculate_composite()
    
    result = MarketComparisonResult(
        nifty_score=nifty_score,
        sensex_score=sensex_score,
        nifty_composite=nifty_composite,
        sensex_composite=sensex_composite
    )
    
    # Determine winner with absolute confidence threshold
    if nifty_composite > sensex_composite:
        difference = nifty_composite - sensex_composite
        if nifty_composite >= 70 and difference >= 5:
            result.winner = "NIFTY"
            result.winner_score = nifty_composite
            result.loser_score = sensex_composite
            result.difference = difference
            result.decision = "SELECT_NIFTY"
            result.reasons = ["NIFTY has superior composite score"]
            result.confidence = nifty_composite
        else:
            result.decision = "NO_TRADE"
            result.reasons = [f"Insufficient edge: NIFTY={nifty_composite:.1f}, SENSEX={sensex_composite:.1f}"]
    else:
        difference = sensex_composite - nifty_composite
        if sensex_composite >= 70 and difference >= 5:
            result.winner = "SENSEX"
            result.winner_score = sensex_composite
            result.loser_score = nifty_composite
            result.difference = difference
            result.decision = "SELECT_SENSEX"
            result.reasons = ["SENSEX has superior composite score"]
            result.confidence = sensex_composite
        else:
            result.decision = "NO_TRADE"
            result.reasons = [f"Insufficient edge: NIFTY={nifty_composite:.1f}, SENSEX={sensex_composite:.1f}"]
    
    return result


def _score_market(market: str, data: Dict) -> MarketScore:
    """Score a single market across all 8 factors."""
    score = MarketScore(market=market)
    
    # 1. Technical Trend (0-100)
    trend = data.get("trend", "SIDEWAYS")
    if trend == "STRONG_BULL":
        score.technical_trend = 90
    elif trend == "BULLISH":
        score.technical_trend = 75
    elif trend == "SIDEWAYS":
        score.technical_trend = 50
    elif trend == "BEARISH":
        score.technical_trend = 25
    else:
        score.technical_trend = 10
    score.factors["technical_trend"] = score.technical_trend
    
    # 2. Momentum (0-100)
    rsi = data.get("rsi", 50)
    if rsi > 70:
        score.momentum = 80
    elif rsi > 60:
        score.momentum = 65
    elif rsi > 40:
        score.momentum = 50
    elif rsi > 30:
        score.momentum = 35
    else:
        score.momentum = 20
    score.factors["momentum"] = score.momentum
    
    # 3. Option Structure (0-100)
    pcr = data.get("pcr", 1.0)
    if 0.8 <= pcr <= 1.2:
        score.option_structure = 80
    elif 0.6 <= pcr < 0.8:
        score.option_structure = 65
    elif 1.2 < pcr <= 1.4:
        score.option_structure = 65
    else:
        score.option_structure = 40
    score.factors["option_structure"] = score.option_structure
    
    # 4. Liquidity (0-100)
    volume = data.get("volume", 0)
    if volume > 1000000:
        score.liquidity = 90
    elif volume > 500000:
        score.liquidity = 75
    elif volume > 100000:
        score.liquidity = 50
    else:
        score.liquidity = 30
    score.factors["liquidity"] = score.liquidity
    
    # 5. Global Alignment (0-100)
    global_trend = data.get("global_trend", "NEUTRAL")
    if global_trend == "BULLISH":
        score.global_alignment = 80
    elif global_trend == "NEUTRAL":
        score.global_alignment = 50
    else:
        score.global_alignment = 20
    score.factors["global_alignment"] = score.global_alignment
    
    # 6. Volatility Quality (0-100)
    vix = data.get("vix", 15)
    if 12 < vix < 18:
        score.volatility_quality = 80
    elif 10 < vix < 22:
        score.volatility_quality = 60
    else:
        score.volatility_quality = 30
    score.factors["volatility_quality"] = score.volatility_quality
    
    # 7. News Alignment (0-100)
    news_sentiment = data.get("news_sentiment", 0)
    score.news_alignment = 50 + (news_sentiment * 30)
    if score.news_alignment > 100:
        score.news_alignment = 100
    elif score.news_alignment < 0:
        score.news_alignment = 0
    score.factors["news_alignment"] = score.news_alignment
    
    # 8. Risk/Reward (0-100)
    rr_ratio = data.get("risk_reward_ratio", 1.0)
    if rr_ratio >= 3.0:
        score.risk_reward = 90
    elif rr_ratio >= 2.0:
        score.risk_reward = 75
    elif rr_ratio >= 1.5:
        score.risk_reward = 60
    elif rr_ratio >= 1.0:
        score.risk_reward = 40
    else:
        score.risk_reward = 20
    score.factors["risk_reward"] = score.risk_reward
    
    return score

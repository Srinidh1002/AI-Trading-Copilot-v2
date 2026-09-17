"""
Full Pre-Market Intelligence - PDF Sections 4-8
All 8 pillars: Global, Economic, News, Institutional, Previous Session, Option Chain, VIX, Regime
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class PreMarketIntelligence:
    """
    Complete Pre-Market Intelligence Engine.
    PDF Sections 4-8 - All 8 pillars.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Cache for performance
        self._cache: Dict[str, Dict] = {}
        self._last_fetch: Dict[str, datetime] = {}
    
    def analyze(self, data: Dict) -> Dict:
        """
        Analyze all pre-market intelligence pillars.
        Returns comprehensive scores and reasons.
        """
        result = {
            "pillars": {},
            "overall_score": 50,
            "reasons": [],
            "blockers": [],
            "status": "READY"
        }
        
        # 1. Global Markets Pillar
        pillar1 = self._analyze_global_markets(data)
        result["pillars"]["global"] = pillar1
        result["reasons"].extend(pillar1.get("reasons", []))
        
        # 2. Economic Calendar Pillar
        pillar2 = self._analyze_economic_calendar(data)
        result["pillars"]["economic"] = pillar2
        result["reasons"].extend(pillar2.get("reasons", []))
        if pillar2.get("blockers"):
            result["blockers"].extend(pillar2.get("blockers", []))
        
        # 3. News Intelligence Pillar
        pillar3 = self._analyze_news(data)
        result["pillars"]["news"] = pillar3
        result["reasons"].extend(pillar3.get("reasons", []))
        
        # 4. Institutional Flow Pillar
        pillar4 = self._analyze_institutional_flow(data)
        result["pillars"]["institutional"] = pillar4
        result["reasons"].extend(pillar4.get("reasons", []))
        
        # 5. Previous Session Pillar
        pillar5 = self._analyze_previous_session(data)
        result["pillars"]["previous_session"] = pillar5
        result["reasons"].extend(pillar5.get("reasons", []))
        
        # 6. Option Chain Pillar
        pillar6 = self._analyze_option_chain(data)
        result["pillars"]["option_chain"] = pillar6
        result["reasons"].extend(pillar6.get("reasons", []))
        
        # 7. VIX Pillar
        pillar7 = self._analyze_vix(data)
        result["pillars"]["vix"] = pillar7
        result["reasons"].extend(pillar7.get("reasons", []))
        
        # 8. Market Regime Pillar
        pillar8 = self._analyze_regime(data)
        result["pillars"]["regime"] = pillar8
        result["reasons"].extend(pillar8.get("reasons", []))
        
        # Calculate overall score
        weights = {
            "global": 0.15,
            "economic": 0.10,
            "news": 0.10,
            "institutional": 0.10,
            "previous_session": 0.10,
            "option_chain": 0.15,
            "vix": 0.10,
            "regime": 0.20
        }
        
        overall = 0
        for pillar, weight in weights.items():
            score = result["pillars"].get(pillar, {}).get("score", 50)
            overall += score * weight
        
        result["overall_score"] = max(0, min(100, overall))
        
        return result
    
    def _analyze_global_markets(self, data: Dict) -> Dict:
        """Pillar 1: Global Markets (US, Asia, Europe)."""
        result = {"score": 50, "reasons": [], "status": "READY"}
        
        global_data = data.get("global_markets", {})
        
        # US Markets
        us_data = global_data.get("us", {})
        if us_data:
            sp500 = us_data.get("sp500", 0)
            nasdaq = us_data.get("nasdaq", 0)
            dow = us_data.get("dow", 0)
            avg_us = (sp500 + nasdaq + dow) / 3 if any([sp500, nasdaq, dow]) else 0
            
            if avg_us > 0.5:
                result["score"] += 15
                result["reasons"].append("US markets bullish")
            elif avg_us < -0.5:
                result["score"] -= 15
                result["reasons"].append("US markets bearish")
        
        # Asia Markets
        asia_data = global_data.get("asia", {})
        if asia_data:
            nikkei = asia_data.get("nikkei", 0)
            hang_seng = asia_data.get("hang_seng", 0)
            avg_asia = (nikkei + hang_seng) / 2 if any([nikkei, hang_seng]) else 0
            
            if avg_asia > 0.5:
                result["score"] += 10
                result["reasons"].append("Asian markets bullish")
            elif avg_asia < -0.5:
                result["score"] -= 10
                result["reasons"].append("Asian markets bearish")
        
        # Europe Markets
        europe_data = global_data.get("europe", {})
        if europe_data:
            ftse = europe_data.get("ftse", 0)
            dax = europe_data.get("dax", 0)
            avg_europe = (ftse + dax) / 2 if any([ftse, dax]) else 0
            
            if avg_europe > 0.5:
                result["score"] += 5
                result["reasons"].append("European markets bullish")
            elif avg_europe < -0.5:
                result["score"] -= 5
                result["reasons"].append("European markets bearish")
        
        result["score"] = max(0, min(100, result["score"]))
        return result
    
    def _analyze_economic_calendar(self, data: Dict) -> Dict:
        """Pillar 2: Economic Calendar (RBI, FOMC, CPI, GDP)."""
        result = {"score": 50, "reasons": [], "blockers": [], "status": "READY"}
        
        events = data.get("economic_events", [])
        
        for event in events:
            impact = event.get("impact", "LOW")
            event_name = event.get("name", "Unknown")
            time_until = event.get("time_until", 9999)
            
            if impact == "CRITICAL":
                if time_until < 1440:  # Within 24 hours
                    result["score"] -= 25
                    result["blockers"].append(f"CRITICAL event: {event_name} in {time_until/60:.1f}h")
                result["reasons"].append(f"Critical economic event: {event_name}")
            elif impact == "HIGH":
                if time_until < 1440:
                    result["score"] -= 15
                    result["reasons"].append(f"High impact event: {event_name} in {time_until/60:.1f}h")
                result["reasons"].append(f"High impact economic event: {event_name}")
            elif impact == "MEDIUM":
                if time_until < 720:
                    result["score"] -= 5
                    result["reasons"].append(f"Medium impact event: {event_name}")
        
        result["score"] = max(0, min(100, result["score"]))
        return result
    
    def _analyze_news(self, data: Dict) -> Dict:
        """Pillar 3: News Intelligence."""
        result = {"score": 50, "reasons": [], "status": "READY"}
        
        news_items = data.get("news", [])
        sentiment_total = 0
        sentiment_count = 0
        high_impact_news = 0
        
        for item in news_items:
            sentiment = item.get("sentiment", 0)
            impact = item.get("impact", "MEDIUM")
            confidence = item.get("confidence", 50)
            
            sentiment_total += sentiment
            sentiment_count += 1
            
            if impact == "HIGH" and confidence > 70:
                high_impact_news += 1
                result["reasons"].append(f"High impact news: {item.get('headline', '')[:50]}...")
        
        if sentiment_count > 0:
            avg_sentiment = sentiment_total / sentiment_count
            result["score"] = 50 + (avg_sentiment * 30)
            
            if avg_sentiment > 0.3:
                result["reasons"].append("Positive overall news sentiment")
            elif avg_sentiment < -0.3:
                result["reasons"].append("Negative overall news sentiment")
        
        if high_impact_news > 2:
            result["score"] -= 10
            result["reasons"].append(f"{high_impact_news} high impact news items")
        
        result["score"] = max(0, min(100, result["score"]))
        return result
    
    def _analyze_institutional_flow(self, data: Dict) -> Dict:
        """Pillar 4: Institutional Flow (FII/DII)."""
        result = {"score": 50, "reasons": [], "status": "READY"}
        
        fii_data = data.get("fii_dii", {})
        fii_net = fii_data.get("fii_net", 0)
        dii_net = fii_data.get("dii_net", 0)
        
        if fii_net != 0:
            if fii_net > 500:
                result["score"] += 15
                result["reasons"].append(f"Strong FII inflow: ₹{fii_net:.0f} cr")
            elif fii_net > 100:
                result["score"] += 5
                result["reasons"].append(f"FII inflow: ₹{fii_net:.0f} cr")
            elif fii_net < -500:
                result["score"] -= 15
                result["reasons"].append(f"Strong FII outflow: ₹{abs(fii_net):.0f} cr")
            elif fii_net < -100:
                result["score"] -= 5
                result["reasons"].append(f"FII outflow: ₹{abs(fii_net):.0f} cr")
        
        if dii_net != 0:
            if dii_net > 500:
                result["score"] += 10
                result["reasons"].append(f"Strong DII inflow: ₹{dii_net:.0f} cr")
        
        result["score"] = max(0, min(100, result["score"]))
        return result
    
    def _analyze_previous_session(self, data: Dict) -> Dict:
        """Pillar 5: Previous Trading Session."""
        result = {"score": 50, "reasons": [], "status": "READY"}
        
        prev_data = data.get("previous_session", {})
        
        if prev_data:
            close = prev_data.get("close", 0)
            open_price = prev_data.get("open", 0)
            high = prev_data.get("high", 0)
            low = prev_data.get("low", 0)
            volume = prev_data.get("volume", 0)
            
            if close > 0 and open_price > 0:
                change_percent = ((close - open_price) / open_price) * 100
                
                if change_percent > 1:
                    result["score"] += 10
                    result["reasons"].append(f"Strong previous session: +{change_percent:.2f}%")
                elif change_percent > 0.5:
                    result["score"] += 5
                    result["reasons"].append(f"Positive previous session: +{change_percent:.2f}%")
                elif change_percent < -1:
                    result["score"] -= 10
                    result["reasons"].append(f"Weak previous session: {change_percent:.2f}%")
                elif change_percent < -0.5:
                    result["score"] -= 5
                    result["reasons"].append(f"Negative previous session: {change_percent:.2f}%")
            
            # Volume analysis
            avg_volume = prev_data.get("avg_volume", volume)
            if avg_volume > 0:
                volume_ratio = volume / avg_volume
                if volume_ratio > 1.5:
                    result["reasons"].append(f"High volume: {volume_ratio:.1f}x avg")
        
        result["score"] = max(0, min(100, result["score"]))
        return result
    
    def _analyze_option_chain(self, data: Dict) -> Dict:
        """Pillar 6: Previous-Day Option Chain."""
        result = {"score": 50, "reasons": [], "status": "READY"}
        
        option_data = data.get("option_chain", {})
        
        if option_data:
            pcr = option_data.get("pcr", 1.0)
            max_pain = option_data.get("max_pain", 0)
            support = option_data.get("support", 0)
            resistance = option_data.get("resistance", 0)
            call_oi = option_data.get("call_oi", 0)
            put_oi = option_data.get("put_oi", 0)
            
            # PCR analysis
            if 0.8 <= pcr <= 1.2:
                result["score"] += 10
                result["reasons"].append(f"PCR balanced: {pcr:.2f}")
            elif pcr > 1.2:
                result["score"] -= 10
                result["reasons"].append(f"PCR bearish: {pcr:.2f}")
            else:
                result["score"] += 10
                result["reasons"].append(f"PCR bullish: {pcr:.2f}")
            
            # Support/Resistance
            if support > 0:
                result["reasons"].append(f"Option support at {support}")
            if resistance > 0:
                result["reasons"].append(f"Option resistance at {resistance}")
        
        result["score"] = max(0, min(100, result["score"]))
        return result
    
    def _analyze_vix(self, data: Dict) -> Dict:
        """Pillar 7: India VIX."""
        result = {"score": 50, "reasons": [], "status": "READY"}
        
        vix = data.get("vix", 15)
        
        if vix > 0:
            if vix < 15:
                result["score"] += 10
                result["reasons"].append(f"Low VIX: {vix:.1f} (low volatility)")
            elif vix < 20:
                result["score"] += 5
                result["reasons"].append(f"Normal VIX: {vix:.1f}")
            elif vix < 25:
                result["score"] -= 5
                result["reasons"].append(f"Elevated VIX: {vix:.1f}")
            else:
                result["score"] -= 15
                result["reasons"].append(f"High VIX: {vix:.1f} (high volatility)")
                result["reasons"].append("Reducing position size due to high VIX")
        
        result["score"] = max(0, min(100, result["score"]))
        return result
    
    def _analyze_regime(self, data: Dict) -> Dict:
        """Pillar 8: Market Regime."""
        result = {"score": 50, "reasons": [], "status": "READY"}
        
        regime = data.get("regime", "RANGE")
        
        regime_scores = {
            "STRONG_BULL": 90,
            "BULL": 80,
            "WEAK_BULL": 65,
            "RANGE": 50,
            "WEAK_BEAR": 35,
            "BEAR": 20,
            "STRONG_BEAR": 10,
            "HIGH_VOLATILITY": 40,
            "EVENT_DRIVEN": 30,
            "UNSTABLE": 20,
        }
        
        score = regime_scores.get(regime, 50)
        result["score"] = score
        result["reasons"].append(f"Market regime: {regime}")
        
        if regime in ["STRONG_BEAR", "BEAR", "UNSTABLE"]:
            result["status"] = "WARNING"
            result["reasons"].append(f"Unfavorable regime: {regime} - caution advised")
        
        return result


def analyze_pre_market(data: Dict) -> Dict:
    """Wrapper function for backward compatibility."""
    engine = PreMarketIntelligence()
    return engine.analyze(data)

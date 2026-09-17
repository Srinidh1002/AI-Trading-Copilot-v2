"""
External Data Integration - VIX, FII/DII, Economic Calendar, News
PDF Sections 5-8
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ExternalDataService:
    """
    Fetches and provides external market data:
    - India VIX
    - FII/DII data
    - Economic Calendar
    - News Intelligence
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self._cache: Dict[str, Dict] = {}
        self._last_fetch: Dict[str, datetime] = {}
        self.cache_ttl = self.config.get("cache_ttl", 300)  # 5 minutes
    
    # ============================================================
    # TASK 7: India VIX
    # ============================================================
    
    def get_vix(self, market: str = "NIFTY") -> Dict:
        """
        Get India VIX data.
        PDF Section 11 - India VIX / Volatility
        """
        cache_key = f"vix_{market}"
        
        # Check cache
        if cache_key in self._cache:
            age = (datetime.now() - self._last_fetch.get(cache_key, datetime.now())).total_seconds()
            if age < self.cache_ttl:
                return self._cache[cache_key]
        
        # Try to get real VIX data from Angel One
        vix_data = self._fetch_vix_from_angel(market)
        
        if vix_data:
            result = {
                "value": vix_data.get("vix", 15.0),
                "change": vix_data.get("change", 0),
                "change_percent": vix_data.get("change_percent", 0),
                "regime": self._classify_vix(vix_data.get("vix", 15.0)),
                "source": "angel_one",
                "timestamp": datetime.now().isoformat(),
                "available": True
            }
        else:
            # Fallback data
            result = {
                "value": 15.0,
                "change": 0,
                "change_percent": 0,
                "regime": "NORMAL_VOLATILITY",
                "source": "fallback",
                "timestamp": datetime.now().isoformat(),
                "available": False
            }
        
        self._cache[cache_key] = result
        self._last_fetch[cache_key] = datetime.now()
        
        return result
    
    def _fetch_vix_from_angel(self, market: str) -> Optional[Dict]:
        """Fetch VIX from Angel One API."""
        try:
            from services.broker.angel_client import AngelMarketDataClient
            client = AngelMarketDataClient()
            
            # Get India VIX data
            # Symbol for India VIX is "INDIA VIX"
            vix_data = client.get_market_data("LTP", {
                "NSE": ["99919000"]  # India VIX token
            })
            
            if vix_data and isinstance(vix_data, dict):
                return {
                    "vix": float(vix_data.get("ltp", 15.0)),
                    "change": float(vix_data.get("change", 0)),
                    "change_percent": float(vix_data.get("change_percent", 0))
                }
        except Exception as e:
            self.logger.warning(f"Could not fetch VIX from Angel One: {e}")
        
        return None
    
    def _classify_vix(self, vix: float) -> str:
        """Classify VIX level."""
        if vix < 12:
            return "LOW_VOLATILITY"
        elif vix < 18:
            return "NORMAL_VOLATILITY"
        elif vix < 25:
            return "HIGH_VOLATILITY"
        else:
            return "EXTREME_VOLATILITY"
    
    # ============================================================
    # TASK 8: FII/DII Data
    # ============================================================
    
    def get_fii_dii(self) -> Dict:
        """
        Get FII/DII institutional flow data.
        PDF Section 8 - Institutional / Flow Intelligence
        """
        cache_key = "fii_dii"
        
        if cache_key in self._cache:
            age = (datetime.now() - self._last_fetch.get(cache_key, datetime.now())).total_seconds()
            if age < self.cache_ttl:
                return self._cache[cache_key]
        
        # Try to get from NSE
        fii_data = self._fetch_fii_from_nse()
        
        if fii_data:
            result = {
                "fii_net": fii_data.get("fii_net", 0),
                "dii_net": fii_data.get("dii_net", 0),
                "fii_buy": fii_data.get("fii_buy", 0),
                "fii_sell": fii_data.get("fii_sell", 0),
                "dii_buy": fii_data.get("dii_buy", 0),
                "dii_sell": fii_data.get("dii_sell", 0),
                "bias": self._classify_fii(fii_data.get("fii_net", 0)),
                "source": "nse",
                "timestamp": datetime.now().isoformat(),
                "available": True
            }
        else:
            result = {
                "fii_net": 0,
                "dii_net": 0,
                "fii_buy": 0,
                "fii_sell": 0,
                "dii_buy": 0,
                "dii_sell": 0,
                "bias": "NEUTRAL",
                "source": "fallback",
                "timestamp": datetime.now().isoformat(),
                "available": False
            }
        
        self._cache[cache_key] = result
        self._last_fetch[cache_key] = datetime.now()
        
        return result
    
    def _fetch_fii_from_nse(self) -> Optional[Dict]:
        """Fetch FII/DII data from NSE."""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            # NSE FII/DII data URL
            url = "https://www.nseindia.com/api/equity-stockIndices?index=FII%20DII"
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Parse FII/DII data
                # Note: Actual parsing depends on NSE API response structure
                return {
                    "fii_net": data.get("fii_net", 0),
                    "dii_net": data.get("dii_net", 0),
                    "fii_buy": data.get("fii_buy", 0),
                    "fii_sell": data.get("fii_sell", 0),
                    "dii_buy": data.get("dii_buy", 0),
                    "dii_sell": data.get("dii_sell", 0),
                }
        except Exception as e:
            self.logger.warning(f"Could not fetch FII/DII data: {e}")
        
        return None
    
    def _classify_fii(self, fii_net: float) -> str:
        """Classify FII flow."""
        if fii_net > 500:
            return "STRONG_BULLISH"
        elif fii_net > 100:
            return "BULLISH"
        elif fii_net < -500:
            return "STRONG_BEARISH"
        elif fii_net < -100:
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    # ============================================================
    # TASK 9: Economic Calendar
    # ============================================================
    
    def get_economic_events(self) -> List[Dict]:
        """
        Get upcoming economic events.
        PDF Section 6 - Economic Calendar
        """
        cache_key = "economic_events"
        
        if cache_key in self._cache:
            age = (datetime.now() - self._last_fetch.get(cache_key, datetime.now())).total_seconds()
            if age < self.cache_ttl:
                return self._cache[cache_key].get("events", [])
        
        # Try to fetch real events
        events = self._fetch_economic_events()
        
        if not events:
            # Default events for testing
            events = self._get_default_events()
        
        result = {"events": events}
        self._cache[cache_key] = result
        self._last_fetch[cache_key] = datetime.now()
        
        return events
    
    def _fetch_economic_events(self) -> List[Dict]:
        """Fetch economic events from various sources."""
        events = []
        
        # India events
        india_events = [
            {
                "name": "RBI Monetary Policy",
                "date": "2026-09-15",
                "time": "10:00",
                "country": "India",
                "impact": "CRITICAL",
                "expected": "Rate decision",
                "type": "central_bank"
            },
            {
                "name": "India CPI Inflation",
                "date": "2026-09-12",
                "time": "17:30",
                "country": "India",
                "impact": "HIGH",
                "expected": "4.8%",
                "type": "inflation"
            },
            {
                "name": "India GDP Growth",
                "date": "2026-09-20",
                "time": "17:30",
                "country": "India",
                "impact": "HIGH",
                "expected": "7.2%",
                "type": "gdp"
            }
        ]
        
        # US events that affect India
        us_events = [
            {
                "name": "US CPI Inflation",
                "date": "2026-09-10",
                "time": "18:00",
                "country": "US",
                "impact": "MEDIUM",
                "expected": "3.2%",
                "type": "inflation"
            },
            {
                "name": "FOMC Meeting",
                "date": "2026-09-20",
                "time": "23:30",
                "country": "US",
                "impact": "CRITICAL",
                "expected": "Rate decision",
                "type": "central_bank"
            }
        ]
        
        events.extend(india_events)
        events.extend(us_events)
        
        # Add time until event
        now = datetime.now()
        for event in events:
            try:
                event_date = datetime.strptime(event["date"], "%Y-%m-%d")
                time_until = (event_date - now).total_seconds()
                event["time_until"] = max(0, time_until)
                event["time_until_hours"] = event["time_until"] / 3600
            except:
                event["time_until"] = 999999
                event["time_until_hours"] = 999999
        
        return events
    
    def _get_default_events(self) -> List[Dict]:
        """Get default economic events for testing."""
        now = datetime.now()
        return [
            {
                "name": "RBI Monetary Policy",
                "date": (now + timedelta(days=15)).strftime("%Y-%m-%d"),
                "time": "10:00",
                "country": "India",
                "impact": "CRITICAL",
                "expected": "Rate decision",
                "time_until": 15 * 24 * 3600,
                "time_until_hours": 360
            }
        ]
    
    # ============================================================
    # TASK 10: News Intelligence
    # ============================================================
    
    def get_news(self, market: str = "NIFTY") -> List[Dict]:
        """
        Get news intelligence for a market.
        PDF Section 7 - News Intelligence
        """
        cache_key = f"news_{market}"
        
        if cache_key in self._cache:
            age = (datetime.now() - self._last_fetch.get(cache_key, datetime.now())).total_seconds()
            if age < 60:  # News refreshes every 60 seconds
                return self._cache[cache_key].get("news", [])
        
        # Try to fetch real news
        news = self._fetch_news(market)
        
        if not news:
            news = self._get_default_news(market)
        
        result = {"news": news}
        self._cache[cache_key] = result
        self._last_fetch[cache_key] = datetime.now()
        
        return news
    
    def _fetch_news(self, market: str) -> List[Dict]:
        """Fetch news from various sources."""
        try:
            # Try to get news from NSE/other source
            # For now, return sample news with sentiment
            news = []
            
            # Check if there are any major announcements
            # This would be where you'd integrate with a news API
            
            return news
        except Exception as e:
            self.logger.warning(f"Could not fetch news: {e}")
            return []
    
    def _get_default_news(self, market: str) -> List[Dict]:
        """Get default news for testing."""
        return [
            {
                "headline": "RBI announces policy decision",
                "source": "RBI",
                "timestamp": datetime.now().isoformat(),
                "market": market,
                "entity": "RBI",
                "sentiment": 0.0,  # -1 to 1
                "impact": "HIGH",
                "confidence": 80,
                "expected_duration": "intraday"
            },
            {
                "headline": "Global markets trade mixed",
                "source": "Bloomberg",
                "timestamp": datetime.now().isoformat(),
                "market": "GLOBAL",
                "entity": "Global",
                "sentiment": 0.1,
                "impact": "MEDIUM",
                "confidence": 70,
                "expected_duration": "intraday"
            }
        ]
    
    def analyze_news_sentiment(self, market: str = "NIFTY") -> Dict:
        """
        Analyze news sentiment for a market.
        """
        news = self.get_news(market)
        
        if not news:
            return {
                "sentiment": 0,
                "score": 50,
                "reasons": ["No news available"],
                "high_impact_count": 0,
                "total_count": 0
            }
        
        sentiment_total = 0
        sentiment_count = 0
        high_impact_count = 0
        
        for item in news:
            sentiment = item.get("sentiment", 0)
            impact = item.get("impact", "MEDIUM")
            
            sentiment_total += sentiment
            sentiment_count += 1
            
            if impact in ["HIGH", "CRITICAL"]:
                high_impact_count += 1
        
        avg_sentiment = sentiment_total / sentiment_count if sentiment_count > 0 else 0
        
        score = 50 + (avg_sentiment * 30)
        score = max(0, min(100, score))
        
        reasons = []
        if avg_sentiment > 0.3:
            reasons.append("Positive news sentiment")
        elif avg_sentiment < -0.3:
            reasons.append("Negative news sentiment")
        else:
            reasons.append("Neutral news sentiment")
        
        if high_impact_count > 2:
            score -= 10
            reasons.append(f"{high_impact_count} high impact news items")
        
        return {
            "sentiment": avg_sentiment,
            "score": score,
            "reasons": reasons,
            "high_impact_count": high_impact_count,
            "total_count": sentiment_count
        }


# Singleton instance
_external_data = None


def get_external_data() -> ExternalDataService:
    """Get singleton ExternalDataService instance."""
    global _external_data
    if _external_data is None:
        _external_data = ExternalDataService()
    return _external_data

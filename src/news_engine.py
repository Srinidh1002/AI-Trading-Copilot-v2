"""News Sentiment - Fetch timestamped headlines from RSS feeds.
No AI hallucination. Real headlines only.
"""
import time
import re
from datetime import datetime, timedelta

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import feedparser
    FEEDPARSER_OK = True
except ImportError:
    FEEDPARSER_OK = False


class NewsEngine:
    # Free RSS feeds (may change over time)
    FEEDS = [
        ("EconomicTimes", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
        ("Moneycontrol", "https://www.moneycontrol.com/rss/latestnews.xml"),
        ("BusinessStandard", "https://www.business-standard.com/rss/markets-106.rss"),
    ]
    
    # Keyword → sentiment
    NEGATIVE_KEYWORDS = [
        "fall", "drop", "crash", "slump", "decline", "loss", "down", "weak",
        "sell-off", "selloff", "bearish", "correction", "slip", "plunge",
        "tumble", "slide", "dip", "concern", "worry", "risk", "fear",
    ]
    POSITIVE_KEYWORDS = [
        "rise", "gain", "surge", "jump", "rally", "up", "strong", "bullish",
        "record", "high", "climb", "advance", "recover", "soar", "boost",
        "optimism", "confident",
    ]
    
    def __init__(self, cache_ttl=1800):
        self.cache_ttl = cache_ttl
        self._cache = None
        self._cache_at = None
    
    def fetch(self, force=False):
        if not force and self._cache and (time.time() - self._cache_at) < self.cache_ttl:
            return self._cache
        
        result = {
            "status": "OK" if FEEDPARSER_OK else "FEEDPARSER_UNAVAILABLE",
            "headlines": [],
            "sentiment_score": 0,
            "sentiment": "NEUTRAL",
            "coverage": "0/0",
            "fetched_at": datetime.now().isoformat(),
        }
        
        if not FEEDPARSER_OK:
            return result
        
        all_headlines = []
        feeds_ok = 0
        
        for name, url in self.FEEDS:
            try:
                feed = feedparser.parse(url)
                if hasattr(feed, "entries") and feed.entries:
                    feeds_ok += 1
                    # Take latest 10 per feed
                    for entry in feed.entries[:10]:
                        title = entry.get("title", "")
                        pub = entry.get("published", "")
                        
                        # Parse published time
                        age_minutes = None
                        try:
                            if pub:
                                # Try common formats
                                from email.utils import parsedate_to_datetime
                                dt = parsedate_to_datetime(pub)
                                age_minutes = (datetime.now(dt.tzinfo) - dt).total_seconds() / 60.0
                        except Exception:
                            pass
                        
                        sentiment = self._classify(title)
                        all_headlines.append({
                            "source": name,
                            "title": title[:200],
                            "published": pub,
                            "age_minutes": round(age_minutes, 1) if age_minutes is not None else None,
                            "sentiment": sentiment,
                        })
            except Exception:
                continue
        
        # Score
        pos = sum(1 for h in all_headlines if h["sentiment"] == "POSITIVE")
        neg = sum(1 for h in all_headlines if h["sentiment"] == "NEGATIVE")
        total = len(all_headlines)
        
        score = pos - neg
        if score > 2:
            sentiment = "BULLISH"
        elif score < -2:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"
        
        result["headlines"] = all_headlines[:20]  # Keep top 20
        result["sentiment_score"] = score
        result["sentiment"] = sentiment
        result["coverage"] = f"{feeds_ok}/{len(self.FEEDS)}"
        result["positive_count"] = pos
        result["negative_count"] = neg
        result["total_count"] = total
        
        self._cache = result
        self._cache_at = time.time()
        return result
    
    def _classify(self, title: str) -> str:
        """Simple keyword-based sentiment."""
        t = title.lower()
        neg_hits = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in t)
        pos_hits = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in t)
        
        if neg_hits > pos_hits:
            return "NEGATIVE"
        elif pos_hits > neg_hits:
            return "POSITIVE"
        return "NEUTRAL"
    
    def describe(self):
        r = self.fetch()
        return (f"News: {r['sentiment']} "
                f"(+{r.get('positive_count', 0)}/-{r.get('negative_count', 0)}/{r.get('total_count', 0)}) "
                f"feeds={r.get('coverage')}")


if __name__ == "__main__":
    eng = NewsEngine()
    r = eng.fetch()
    print(f"Status: {r['status']}")
    print(f"Feeds: {r['coverage']}")
    print(f"Sentiment: {r['sentiment']} (score={r['sentiment_score']})")
    print(f"Counts: +{r.get('positive_count', 0)} / -{r.get('negative_count', 0)} / total {r.get('total_count', 0)}")
    print()
    print("Sample headlines:")
    for h in r.get("headlines", [])[:5]:
        print(f"  [{h['source']}] {h['sentiment']:9s} {h['title'][:100]}")

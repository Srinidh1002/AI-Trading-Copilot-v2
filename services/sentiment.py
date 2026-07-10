"""Keyword-based sentiment analysis for financial news headlines."""

import re
from collections.abc import Mapping

from services.news import get_stock_news


POSITIVE_WORDS = {
    "gain",
    "growth",
    "profit",
    "record",
    "beat",
    "bullish",
    "upgrade",
    "strong",
    "surge",
    "buy",
    "expansion",
    "partnership",
    "innovation",
    "success",
    "launch",
}

NEGATIVE_WORDS = {
    "loss",
    "lawsuit",
    "decline",
    "fall",
    "bearish",
    "downgrade",
    "weak",
    "cut",
    "miss",
    "fraud",
    "bankruptcy",
    "investigation",
    "recall",
    "delay",
    "drop",
}


def _no_news_result() -> dict[str, int | str]:
    """Return the standard response for unavailable news."""
    return {"bull": 0, "bear": 0, "score": 50, "summary": "No recent news"}


def _headline_counts(title: object) -> tuple[int, int]:
    """Count positive and negative sentiment words in a headline."""
    if not isinstance(title, str):
        return 0, 0

    words = re.findall(r"\b\w+\b", title.casefold())
    positive = sum(word in POSITIVE_WORDS for word in words)
    negative = sum(word in NEGATIVE_WORDS for word in words)
    return positive, negative


def _summary(bull: int, bear: int) -> str:
    """Return a readable sentiment summary from directional article counts."""
    if bull > bear:
        return "Mostly Positive"
    if bear > bull:
        return "Mostly Negative"
    return "Neutral"


def sentiment_score(symbol: str = "AAPL") -> dict[str, int | str]:
    """Analyze recent stock-news titles for simple bullish or bearish sentiment.

    Args:
        symbol: Yahoo Finance ticker symbol.

    Returns:
        Counts of bullish and bearish articles, a bull-percentage score, and a
        concise sentiment summary.
    """
    try:
        news = get_stock_news(symbol)
        if not isinstance(news, list) or not news:
            return _no_news_result()

        bull = 0
        bear = 0
        total = 0

        for article in news:
            total += 1
            title = article.get("title") if isinstance(article, Mapping) else ""
            positive, negative = _headline_counts(title)

            if positive > negative:
                bull += 1
            elif negative > positive:
                bear += 1

        if total == 0:
            return _no_news_result()

        score = int((bull / total) * 100)
        return {
            "bull": bull,
            "bear": bear,
            "score": score,
            "summary": _summary(bull, bear),
        }
    except Exception:
        return _no_news_result()

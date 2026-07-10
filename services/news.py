"""Yahoo Finance news retrieval for stock symbols."""

from collections.abc import Mapping
from typing import Any

import yfinance as yf


def _text(value: object) -> str:
    """Convert an optional value to a safe, stripped string."""
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _value_from(
    primary: Mapping[str, Any], fallback: Mapping[str, Any], *keys: str
) -> object:
    """Return the first non-null value from two possible news payloads."""
    for source in (primary, fallback):
        for key in keys:
            value = source.get(key)
            if value is not None:
                return value
    return None


def _url(value: object) -> str:
    """Extract a URL from either a string or Yahoo's nested URL structure."""
    if isinstance(value, Mapping):
        return _text(value.get("url"))
    return _text(value)


def _normalise_article(article: object) -> dict[str, str] | None:
    """Convert a Yahoo Finance news item to the public news schema."""
    if not isinstance(article, Mapping):
        return None

    content = article.get("content")
    primary: Mapping[str, Any] = content if isinstance(content, Mapping) else article
    fallback: Mapping[str, Any] = article

    provider = _value_from(primary, fallback, "provider", "publisher")
    if isinstance(provider, Mapping):
        publisher = _text(provider.get("displayName") or provider.get("name"))
    else:
        publisher = _text(provider)

    link_value = _value_from(
        primary,
        fallback,
        "canonicalUrl",
        "clickThroughUrl",
        "link",
        "url",
    )

    return {
        "title": _text(_value_from(primary, fallback, "title")),
        "publisher": publisher,
        "link": _url(link_value),
        "published": _text(
            _value_from(
                primary,
                fallback,
                "pubDate",
                "providerPublishTime",
                "published",
            )
        ),
        "summary": _text(
            _value_from(primary, fallback, "summary", "description")
        ),
    }


def get_stock_news(symbol: str, limit: int = 10) -> list[dict[str, str]]:
    """Return the latest Yahoo Finance news articles for a stock symbol.

    Args:
        symbol: Yahoo Finance ticker symbol.
        limit: Maximum number of articles to return.

    Returns:
        Normalised news dictionaries. Returns an empty list if news cannot be
        retrieved or is unavailable.
    """
    try:
        if not isinstance(symbol, str) or not symbol.strip():
            return []

        safe_limit = max(int(limit), 0)
        if safe_limit == 0:
            return []

        articles = yf.Ticker(symbol.strip()).news
        if not isinstance(articles, list):
            return []

        news: list[dict[str, str]] = []
        for article in articles[:safe_limit]:
            try:
                normalised = _normalise_article(article)
                if normalised is not None:
                    news.append(normalised)
            except Exception:
                continue

        return news
    except Exception:
        return []

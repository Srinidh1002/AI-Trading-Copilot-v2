"""
News Sentiment Engine

Institutional news sentiment analysis.
"""

from collections import Counter


POSITIVE = {

    "buy",
    "bullish",
    "growth",
    "strong",
    "positive",
    "record",
    "profit",
    "gain",
    "up",
    "surge",
    "beat",
    "approval",
    "expansion",
    "optimistic",
    "recovery",
    "breakout",

}

NEGATIVE = {

    "sell",
    "bearish",
    "loss",
    "weak",
    "negative",
    "fall",
    "down",
    "drop",
    "crash",
    "miss",
    "downgrade",
    "recession",
    "fear",
    "inflation",
    "war",
    "bankruptcy",
    "decline",

}


def analyze_news_sentiment(snapshot):

    """
    Expected snapshot:

    snapshot["news"] = [

        {
            "title": "...",
            "summary": "...",
        },

    ]
    """

    news = snapshot.get(
        "news",
        [],
    )

    if not news:

        return {

            "signal": "UNKNOWN",

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "reason": "No news available",

            "metrics": {},

        }

    positive = 0
    negative = 0

    words = Counter()

    for item in news:

        text = (

            f"{item.get('title','')} "

            f"{item.get('summary','')}"

        ).lower()

        tokens = text.split()

        words.update(tokens)

        for token in tokens:

            token = token.strip(
                ".,!?():;'\""
            )

            if token in POSITIVE:

                positive += 1

            elif token in NEGATIVE:

                negative += 1

    bull = 0
    bear = 0

    reasons = []

    if positive > negative:

        bull += min(
            5,
            positive,
        )

        reasons.append(
            "Positive News Flow"
        )

    elif negative > positive:

        bear += min(
            5,
            negative,
        )

        reasons.append(
            "Negative News Flow"
        )

    if bull >= bear + 2:

        signal = "BULLISH"

    elif bear >= bull + 2:

        signal = "BEARISH"

    else:

        signal = "NEUTRAL"

    confidence = min(

        100,

        round(

            50

            + abs(
                positive - negative
            ) * 5,

            2,

        ),

    )

    top_keywords = [

        word

        for word, _ in words.most_common(10)

    ]

    return {

        "signal": signal,

        "bull_score": bull,

        "bear_score": bear,

        "confidence": confidence,

        "reason": ", ".join(reasons),

        "metrics": {

            "Positive": positive,

            "Negative": negative,

            "TopKeywords": top_keywords,

        },

    }
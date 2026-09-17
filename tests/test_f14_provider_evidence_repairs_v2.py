from __future__ import annotations

import sys
from pathlib import Path
from types import MethodType

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from provider_injected_target_bot_v2 import (  # noqa: E402
    ProviderInjectedUnifiedTradingBotV2,
)
from target_focused_bot import UnifiedTradingBot  # noqa: E402


def test_injected_early_wait_backfills_premarket_without_changing_result(monkeypatch):
    bot = object.__new__(ProviderInjectedUnifiedTradingBotV2)
    bot._last_premarket_state = None
    sentinel = object()

    monkeypatch.setattr(
        UnifiedTradingBot,
        "get_enhanced_sentiment",
        lambda self, spot, options: "NEUTRAL",
    )
    bot._build_premarket_backfill = MethodType(lambda self: sentinel, bot)

    result = ProviderInjectedUnifiedTradingBotV2.get_enhanced_sentiment(
        bot,
        23270.0,
        [],
    )

    assert result == "NEUTRAL"
    assert bot._last_premarket_state is sentinel


def test_injected_success_path_does_not_replace_existing_premarket(monkeypatch):
    bot = object.__new__(ProviderInjectedUnifiedTradingBotV2)
    existing = object()
    bot._last_premarket_state = existing
    calls = []

    monkeypatch.setattr(
        UnifiedTradingBot,
        "get_enhanced_sentiment",
        lambda self, spot, options: "BULLISH",
    )
    bot._build_premarket_backfill = MethodType(
        lambda self: calls.append("unexpected") or object(),
        bot,
    )

    result = ProviderInjectedUnifiedTradingBotV2.get_enhanced_sentiment(
        bot,
        23270.0,
        [{"type": "CE"}],
    )

    assert result == "BULLISH"
    assert bot._last_premarket_state is existing
    assert calls == []

"""Unified weighted AI decision engine for technical, market, option and news inputs."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from collections.abc import Mapping
from typing import Any

from services.database import get_connection, log_decision
from services.market_engine import market_score
from services.option_ai import option_score
from services.sentiment import sentiment_score
from services.strategy_engine import strategy_engine

logger = logging.getLogger(__name__)
WEIGHTS = {"technical": 0.35, "market": 0.30, "option": 0.25, "sentiment": 0.10}


def _value(data: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        try: return float(data.get(key, default))
        except (TypeError, ValueError): continue
    return default


def _directional_percent(data: Mapping[str, Any]) -> tuple[float, float]:
    bull, bear = _value(data, "bull_score", "bull"), _value(data, "bear_score", "bear")
    total = bull + bear
    return (50.0, 50.0) if total <= 0 else (bull * 100 / total, bear * 100 / total)


def _technical_indicators(technical: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = technical.get("indicators")
    return nested if isinstance(nested, Mapping) else technical


def _log_result(timestamp: str, symbol: str, indicators: Mapping[str, Any], decision: Mapping[str, Any], bull: float, bear: float, confidence: float, trend: str, reasons: list[str]) -> None:
    log_decision({"timestamp": timestamp, "symbol": symbol, "price": _value(indicators, "CURRENT_PRICE", "price"), "signal": decision.get("signal", "HOLD"), "confidence": confidence, "bull_score": bull, "bear_score": bear, "neutral_score": 100 - confidence, "entry": _value(indicators, "ENTRY", "CURRENT_PRICE"), "stop_loss": _value(indicators, "STOP_LOSS"), "target1": _value(indicators, "TARGET1"), "target2": _value(indicators, "TARGET2"), "support": _value(indicators, "SUPPORT"), "resistance": _value(indicators, "RESISTANCE"), "trend": trend, "pattern": "", "reason": "; ".join(reasons), "rsi": _value(indicators, "RSI"), "adx": _value(indicators, "ADX"), "atr": _value(indicators, "ATR"), "ema20": _value(indicators, "EMA20"), "ema50": _value(indicators, "EMA50"), "ema200": _value(indicators, "EMA200"), "macd": _value(indicators, "MACD"), "macd_signal": _value(indicators, "MACD_SIGNAL"), "vwap": _value(indicators, "VWAP")})


def _create_paper_trade(timestamp: str, decision: Mapping[str, Any], indicators: Mapping[str, Any], confidence: float, reason: str) -> dict[str, Any]:
    signal = str(decision.get("signal", "HOLD")).upper()
    if signal not in {"BUY", "SELL"}: return {"created": False, "reason": "NO_ACTIONABLE_SIGNAL"}
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE status = 'OPEN' AND signal = ?", (signal,))
        if int(cursor.fetchone()[0]) > 0: return {"created": False, "reason": "DUPLICATE_OPEN_TRADE"}
        cursor.execute("INSERT INTO paper_trades(timestamp, signal, status, entry, stop_loss, target1, target2, exit_price, pnl, confidence, reason, duration) VALUES (?, ?, 'OPEN', ?, ?, ?, ?, NULL, NULL, ?, ?, '')", (timestamp, signal, _value(indicators, "ENTRY", "CURRENT_PRICE"), _value(indicators, "STOP_LOSS"), _value(indicators, "TARGET1"), _value(indicators, "TARGET2"), confidence, reason))
        conn.commit()
        return {"created": True, "trade_id": cursor.lastrowid, "reason": "PAPER_TRADE_CREATED"}
    except Exception as exc:
        conn.rollback(); logger.exception("Paper-trade creation failed")
        return {"created": False, "reason": "PAPER_TRADE_ERROR", "error": str(exc)}
    finally: conn.close()


def ai_engine(technical: Mapping[str, Any], symbol: str = "NIFTY", option_data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Combine already-computed technical output with live market, option and sentiment scores."""
    if not isinstance(technical, Mapping): raise TypeError("technical must be the dictionary returned by technical_score().")
    market, option, sentiment = market_score(technical), option_score(symbol=symbol, option_data=option_data), sentiment_score(symbol)
    strategy = strategy_engine(technical=technical, market=market, option=option, sentiment=sentiment)
    components = {"technical": technical, "market": market, "option": option, "sentiment": sentiment}
    bull = round(sum(_directional_percent(result)[0] * WEIGHTS[name] for name, result in components.items()), 2)
    bear = round(sum(_directional_percent(result)[1] * WEIGHTS[name] for name, result in components.items()), 2)
    confidence, trend = round(abs(bull - bear), 2), "BULLISH" if bull > bear else "BEARISH" if bear > bull else "NEUTRAL"
    recommendation = "BUY" if bull >= 60 and confidence >= 15 else "SELL" if bear >= 60 and confidence >= 15 else "HOLD"
    decision = dict(strategy); decision.update({"signal": recommendation, "recommendation": recommendation, "confidence": confidence, "trend": trend})
    indicators, timestamp = _technical_indicators(technical), datetime.now(timezone.utc).isoformat()
    reasons = [f"Weighted {name}: {round(_directional_percent(result)[0] - _directional_percent(result)[1], 2)}" for name, result in components.items()]
    try: _log_result(timestamp, symbol, indicators, decision, bull, bear, confidence, trend, reasons)
    except Exception: logger.exception("Decision logging failed")
    paper_trade = _create_paper_trade(timestamp, decision, indicators, confidence, "; ".join(reasons))
    return {"technical": technical, "market": market, "sentiment": sentiment, "option": option, "strategy": strategy, "decision": decision, "bull_score": bull, "bear_score": bear, "confidence": confidence, "dominant_trend": trend, "recommendation": recommendation, "paper_trade": paper_trade, "timestamp": timestamp}

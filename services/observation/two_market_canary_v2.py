"""Read-only two-market observational canary for the provider-injected bot.

The canary executes existing analysis code while diverting prediction-ledger
writes into memory. It never opens/closes a position, increments PAPER
certification, submits orders, or provides provider fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MethodType
from typing import Any, Mapping


class CanaryObservationError(RuntimeError):
    """Required observational evidence could not be produced safely."""


@dataclass(frozen=True)
class CanaryMarketResultV2:
    market: str
    connected: bool
    spot: float
    expiry: str | None
    atm: float
    option_count: int
    chain_status: str | None
    chain_reason: str | None
    chain_request_count: int | None
    chain_depth_fanout: int | None
    pcr_oi: float | None
    mtf_consensus: str
    regime: str
    prediction: Mapping[str, Any]
    diagnostic_candidate: Mapping[str, Any] | None
    executable_quote: Mapping[str, Any] | None
    paper_fill: float | None
    lot_size: int | None
    lots_affordable: int | None
    targets: Mapping[str, float] | None
    websocket_status: str
    websocket_healthy: bool
    counters_unchanged: bool
    premarket_available: bool
    provider_mode: str

    def selector_context(self) -> dict[str, Any]:
        candidate_score = 0.0
        if isinstance(self.diagnostic_candidate, Mapping):
            try:
                candidate_score = float(self.diagnostic_candidate.get("score") or 0.0)
            except (TypeError, ValueError):
                candidate_score = 0.0
        try:
            coverage = float(self.prediction.get("coverage_pct") or 0.0)
        except (TypeError, ValueError):
            coverage = 0.0
        return {
            "evidence_coverage_pct": coverage,
            "bias_confidence": str(self.prediction.get("bias_confidence") or "WEAK"),
            "regime": self.regime,
            "top_strike_score": candidate_score,
            "readiness": str(self.prediction.get("readiness") or "BLOCKED"),
        }


def has_complete_canary_market_evidence(result: CanaryMarketResultV2) -> bool:
    """Require a complete read-only chain and execution probe for one market.

    A safe abstention on an unavailable chain remains safe, but cannot prove
    the two-market F14 exit gate.
    """
    quote = result.executable_quote
    targets = result.targets
    try:
        bid = float(quote.get("bid")) if isinstance(quote, Mapping) else 0.0
        ask = float(quote.get("ask")) if isinstance(quote, Mapping) else 0.0
    except (TypeError, ValueError):
        return False
    return bool(
        result.connected
        and result.provider_mode == "FYERS_V2_INJECTED"
        and result.spot > 0
        and isinstance(result.expiry, str)
        and bool(result.expiry.strip())
        and result.atm > 0
        and result.chain_status == "OK"
        and result.option_count > 0
        and result.chain_request_count == 1
        and result.chain_depth_fanout == 0
        and result.pcr_oi is not None
        and result.diagnostic_candidate is not None
        and bid > 0
        and ask > bid
        and result.paper_fill is not None
        and result.paper_fill > 0
        and result.lot_size is not None
        and result.lot_size > 0
        and result.lots_affordable is not None
        and result.lots_affordable > 0
        and isinstance(targets, Mapping)
        and all(targets.get(name) is not None for name in ("sl", "t1", "t2", "t3"))
        and result.websocket_healthy
        and result.counters_unchanged
        and result.prediction.get("persisted_to_disk") is False
        and result.premarket_available
    )


def _counter_snapshot(bot) -> tuple[int, int, int, int, int]:
    return (
        int(getattr(bot, "current_session", 0) or 0),
        int(getattr(bot, "total_trades", 0) or 0),
        int(getattr(bot, "certification_counter", 0) or 0),
        len(getattr(bot, "active_trades", {}) or {}),
        len(getattr(bot, "completed_trades", []) or []),
    )


def _install_memory_prediction_sink(bot) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def _memory_persist(self, **kwargs):
        captured.clear()
        captured.update(kwargs)
        captured["persisted_to_disk"] = False
        return True

    bot._persist_prediction = MethodType(_memory_persist, bot)
    return captured


def _rank_diagnostic_candidate(bot, chain, prediction, atm):
    if not isinstance(chain, Mapping) or chain.get("status") != "OK":
        return None

    bias = str(prediction.get("bias") or "NEUTRAL").upper()
    directions = [bias] if bias in {"BULLISH", "BEARISH"} else ["BULLISH", "BEARISH"]
    top = []
    for direction in directions:
        ranking = bot.strike_ranker.rank(chain, direction, atm)
        if not isinstance(ranking, Mapping):
            continue
        candidate = ranking.get("top_pick")
        if isinstance(candidate, Mapping):
            item = dict(candidate)
            item["diagnostic_direction"] = direction
            top.append(item)
    if not top:
        return None
    top.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return top[0]


def _probe_execution(bot, candidate, expiry):
    if not isinstance(candidate, Mapping):
        return None, None, None, None, None
    symbol = candidate.get("symbol")
    token = candidate.get("token")
    if not symbol or not token:
        return None, None, None, None, None

    quote = bot._fetch_option_quote_full(str(symbol), str(token))
    if not isinstance(quote, Mapping):
        return None, None, None, None, None
    try:
        ltp = float(quote.get("ltp") or 0.0)
        bid = float(quote.get("bid") or 0.0)
        ask = float(quote.get("ask") or 0.0)
    except (TypeError, ValueError):
        return dict(quote), None, None, None, None
    if ltp <= 0 or bid <= 0 or ask <= bid:
        return dict(quote), None, None, None, None

    fill, status = bot.capital_engine.compute_paper_fill(bid, ask, ltp, direction="BUY")
    if status != "OK" or fill is None:
        return dict(quote), None, None, None, None

    from contract_metadata import resolve_lot_size

    lot_size, _source = resolve_lot_size(
        bot.contract_index,
        bot.market,
        expiry,
        float(candidate.get("strike") or 0.0),
        str(candidate.get("type") or ""),
    )
    if lot_size is None or lot_size <= 0:
        return dict(quote), float(fill), None, None, None

    lots = bot.capital_engine.compute_lot_size(float(fill), int(lot_size))
    targets = {
        "sl": round(float(fill) * (1 - bot.STOP_LOSS_PERCENT / 100.0), 4),
        "t1": round(float(fill) * (1 + bot.T1_PERCENT / 100.0), 4),
        "t2": round(float(fill) * (1 + bot.T2_PERCENT / 100.0), 4),
        "t3": round(float(fill) * (1 + bot.T3_PERCENT / 100.0), 4),
    }
    return dict(quote), float(fill), int(lot_size), int(lots), targets


def observe_market_v2(bot) -> CanaryMarketResultV2:
    """Execute one analysis observation without PAPER or ledger mutation."""
    if getattr(bot, "provider_mode", None) != "FYERS_V2_INJECTED":
        raise CanaryObservationError("FYERS_INJECTED_BOT_REQUIRED")
    if getattr(bot, "data_only", None) is not True:
        raise CanaryObservationError("DATA_ONLY_BOUNDARY_REQUIRED")

    before = _counter_snapshot(bot)
    captured_prediction = _install_memory_prediction_sink(bot)

    connected = bot.connect_with_retry(max_retries=1, retry_delay=0)
    if not connected:
        raise CanaryObservationError(f"{bot.market}_CONNECT_FAILED")
    if not bot.load_instruments():
        raise CanaryObservationError(f"{bot.market}_INSTRUMENT_LOAD_FAILED")

    spot = float(bot.get_spot() or 0.0)
    if spot <= 0:
        raise CanaryObservationError(f"{bot.market}_SPOT_UNAVAILABLE")

    expiry = bot.get_expiry()
    options, atm = bot.get_options(spot, expiry)
    chain = getattr(bot, "_last_chain", None)

    # This calls the existing production analysis stack. Prediction persistence
    # was replaced above with an in-memory sink, so no ledger file is written.
    bot.get_enhanced_sentiment(spot, options)

    if not captured_prediction:
        captured_prediction.update(
            {
                "bias": "NEUTRAL",
                "bias_confidence": "WEAK",
                "readiness": getattr(bot, "decision_state", "BLOCKED"),
                "action": "WAIT",
                "blockers": ["CANARY_PREDICTION_NOT_CAPTURED"],
                "coverage_pct": 0.0,
                "regime": (getattr(bot, "_last_regime_ctx", {}) or {}).get(
                    "regime", "UNKNOWN"
                ),
                "persisted_to_disk": False,
            }
        )

    mtf = bot.market_intel.get_multi_timeframe_technicals() if bot.market_intel else {}
    mtf_consensus = str((mtf or {}).get("consensus") or "UNKNOWN")
    regime = str(
        captured_prediction.get("regime")
        or (getattr(bot, "_last_regime_ctx", {}) or {}).get("regime")
        or "UNKNOWN"
    )

    candidate = _rank_diagnostic_candidate(bot, chain, captured_prediction, atm)
    quote, fill, lot_size, lots, targets = _probe_execution(bot, candidate, expiry)

    ws_status = bot.ws_feed.health_str() if bot.ws_feed else "OFFLINE"
    ws_healthy = bool(getattr(bot, "ws_healthy", False)) and ws_status == "HEALTHY"
    after = _counter_snapshot(bot)

    chain_status = chain.get("status") if isinstance(chain, Mapping) else None
    chain_reason = chain.get("reason") if isinstance(chain, Mapping) else None
    chain_request_count = chain.get("request_count") if isinstance(chain, Mapping) else None
    chain_depth_fanout = (
        chain.get("per_contract_depth_requests") if isinstance(chain, Mapping) else None
    )
    pcr_oi = chain.get("pcr_oi") if isinstance(chain, Mapping) else None

    return CanaryMarketResultV2(
        market=str(bot.market),
        connected=connected,
        spot=spot,
        expiry=expiry,
        atm=float(atm or 0.0),
        option_count=len(options or []),
        chain_status=str(chain_status) if chain_status is not None else None,
        chain_reason=str(chain_reason) if chain_reason is not None else None,
        chain_request_count=(
            int(chain_request_count) if isinstance(chain_request_count, int) else None
        ),
        chain_depth_fanout=(
            int(chain_depth_fanout) if isinstance(chain_depth_fanout, int) else None
        ),
        pcr_oi=float(pcr_oi) if isinstance(pcr_oi, (int, float)) else None,
        mtf_consensus=mtf_consensus,
        regime=regime,
        prediction=dict(captured_prediction),
        diagnostic_candidate=dict(candidate) if isinstance(candidate, Mapping) else None,
        executable_quote=quote,
        paper_fill=fill,
        lot_size=lot_size,
        lots_affordable=lots,
        targets=targets,
        websocket_status=ws_status,
        websocket_healthy=ws_healthy,
        counters_unchanged=before == after,
        premarket_available=getattr(bot, "_last_premarket_state", None) is not None,
        provider_mode=str(getattr(bot, "provider_mode", "UNKNOWN")),
    )


def select_market_v2(nifty: CanaryMarketResultV2, sensex: CanaryMarketResultV2):
    from market_selector import MarketSelector

    return MarketSelector().select(
        nifty.selector_context(),
        sensex.selector_context(),
    )

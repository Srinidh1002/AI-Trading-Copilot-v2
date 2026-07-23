"""Option-chain intelligence scoring with graceful degradation for partial chains."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from collections.abc import Mapping, Sequence
from typing import Any

from services.analysis.option_chain import get_option_chain

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OptionScoreConfig:
    pcr_weight: float = 15.0
    oi_weight: float = 20.0
    writing_weight: float = 15.0
    max_pain_weight: float = 10.0
    premium_weight: float = 10.0
    iv_weight: float = 10.0
    greeks_weight: float = 10.0
    liquidity_weight: float = 10.0
    bullish_pcr: float = 1.05
    bearish_pcr: float = 0.80


class OptionScoreEngine:
    def __init__(self, config: OptionScoreConfig | None = None) -> None:
        self.config = config or OptionScoreConfig()

    @staticmethod
    def _number(data: Mapping[str, Any], *names: str) -> float | None:
        for name in names:
            try:
                value = float(data.get(name))
                if math.isfinite(value): return value
            except (TypeError, ValueError):
                pass
        return None

    @staticmethod
    def _contracts(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        contracts = data.get("contracts", data.get("data", []))
        return [item for item in contracts if isinstance(item, Mapping)] if isinstance(contracts, Sequence) and not isinstance(contracts, (str, bytes)) else []

    @staticmethod
    def _result(weight: float, bull: float = 0, bear: float = 0, reason: str | None = None) -> tuple[float, float, list[str]]:
        return round(min(weight, max(0, bull)), 2), round(min(weight, max(0, bear)), 2), [reason] if reason else []

    def score_pcr(self, chain: Mapping[str, Any]) -> tuple[float, float, list[str]]:
        pcr = self._number(chain, "PCR", "pcr")
        if pcr is None: return self._result(self.config.pcr_weight, reason="PCR unavailable")
        if pcr >= self.config.bullish_pcr: return self._result(self.config.pcr_weight, bull=self.config.pcr_weight, reason="Put-call ratio supports bulls")
        if pcr <= self.config.bearish_pcr: return self._result(self.config.pcr_weight, bear=self.config.pcr_weight, reason="Put-call ratio supports bears")
        return self._result(self.config.pcr_weight, self.config.pcr_weight / 2, self.config.pcr_weight / 2, "Put-call ratio is balanced")

    def score_open_interest(self, chain: Mapping[str, Any]) -> tuple[float, float, list[str]]:
        calls, puts = self._number(chain, "call_oi", "CALL_OI"), self._number(chain, "put_oi", "PUT_OI")
        if calls is None or puts is None or calls + puts <= 0: return self._result(self.config.oi_weight, reason="Aggregate open interest unavailable")
        if puts > calls: return self._result(self.config.oi_weight, bull=self.config.oi_weight, reason="Put open interest exceeds call open interest")
        if calls > puts: return self._result(self.config.oi_weight, bear=self.config.oi_weight, reason="Call open interest exceeds put open interest")
        return self._result(self.config.oi_weight, self.config.oi_weight / 2, self.config.oi_weight / 2, "Open-interest structure is balanced")

    def score_writing(self, chain: Mapping[str, Any]) -> tuple[float, float, list[str]]:
        contracts = self._contracts(chain)
        call_change = sum(self._number(item, "oi_change", "change_in_oi") or 0 for item in contracts if str(item.get("option_type", "")).upper() == "CE")
        put_change = sum(self._number(item, "oi_change", "change_in_oi") or 0 for item in contracts if str(item.get("option_type", "")).upper() == "PE")
        if not contracts or call_change == put_change == 0: return self._result(self.config.writing_weight, reason="Option-writing data unavailable")
        if put_change > call_change: return self._result(self.config.writing_weight, bull=self.config.writing_weight, reason="Put writing provides downside support")
        return self._result(self.config.writing_weight, bear=self.config.writing_weight, reason="Call writing creates overhead resistance")

    def score_max_pain(self, chain: Mapping[str, Any]) -> tuple[float, float, list[str]]:
        spot, pain = self._number(chain, "spot", "spot_price", "underlyingValue"), self._number(chain, "max_pain", "MAX_PAIN")
        if spot is None or pain is None or spot <= 0: return self._result(self.config.max_pain_weight, reason="Max-pain comparison unavailable")
        if spot < pain: return self._result(self.config.max_pain_weight, bull=self.config.max_pain_weight, reason="Spot trades below max pain")
        if spot > pain: return self._result(self.config.max_pain_weight, bear=self.config.max_pain_weight, reason="Spot trades above max pain")
        return self._result(self.config.max_pain_weight, self.config.max_pain_weight / 2, self.config.max_pain_weight / 2, "Spot is at max pain")

    def _contract_direction(self, chain: Mapping[str, Any], field: str, weight: float, label: str) -> tuple[float, float, list[str]]:
        contracts = self._contracts(chain)
        call = [self._number(item, field) for item in contracts if str(item.get("option_type", "")).upper() == "CE"]
        put = [self._number(item, field) for item in contracts if str(item.get("option_type", "")).upper() == "PE"]
        call_values, put_values = [x for x in call if x is not None], [x for x in put if x is not None]
        if not call_values or not put_values: return self._result(weight, reason=f"{label} data unavailable")
        if sum(call_values) / len(call_values) > sum(put_values) / len(put_values): return self._result(weight, bull=weight, reason=f"Call {label.lower()} is stronger")
        return self._result(weight, bear=weight, reason=f"Put {label.lower()} is stronger")

    def score_premium(self, chain: Mapping[str, Any]) -> tuple[float, float, list[str]]: return self._contract_direction(chain, "premium_change", self.config.premium_weight, "premium behaviour")
    def score_iv(self, chain: Mapping[str, Any]) -> tuple[float, float, list[str]]: return self._contract_direction(chain, "iv", self.config.iv_weight, "implied volatility")

    def score_greeks(self, chain: Mapping[str, Any]) -> tuple[float, float, list[str]]:
        contracts = self._contracts(chain)
        deltas = [self._number(item, "delta") for item in contracts]
        valid = [delta for delta in deltas if delta is not None]
        if not valid: return self._result(self.config.greeks_weight, reason="Greeks unavailable")
        directional = sum(valid) / len(valid)
        return self._result(self.config.greeks_weight, bull=self.config.greeks_weight if directional > 0 else 0, bear=self.config.greeks_weight if directional < 0 else 0, reason="Aggregate option delta is directional")

    def score_liquidity(self, chain: Mapping[str, Any]) -> tuple[float, float, list[str]]:
        contracts = self._contracts(chain)
        liquid = [item for item in contracts if (self._number(item, "volume") or 0) > 0 and (self._number(item, "bid") or 0) > 0 and (self._number(item, "ask") or 0) > 0]
        if not contracts: return self._result(self.config.liquidity_weight, reason="Liquidity data unavailable")
        score = self.config.liquidity_weight * len(liquid) / len(contracts)
        return self._result(self.config.liquidity_weight, score / 2, score / 2, "Option-chain liquidity assessed")

    def option_score(self, chain: Mapping[str, Any] | None = None, symbol: str = "NIFTY") -> dict[str, Any]:
        if chain is None:
            try: chain = get_option_chain(symbol)
            except Exception as exc: logger.exception("Option-chain retrieval failed for %s", symbol); chain = {"error": str(exc)}
        data = chain if isinstance(chain, Mapping) else {}
        methods = {"pcr": self.score_pcr, "open_interest": self.score_open_interest, "writing": self.score_writing, "max_pain": self.score_max_pain, "premium": self.score_premium, "iv": self.score_iv, "greeks": self.score_greeks, "liquidity": self.score_liquidity}
        categories = {name: method(data) for name, method in methods.items()}
        bull, bear = round(sum(item[0] for item in categories.values()), 2), round(sum(item[1] for item in categories.values()), 2)
        evidence = sum(bool(item[2] and "unavailable" not in item[2][0].lower()) for item in categories.values())
        return {"bull_score": bull, "bear_score": bear, "bull": bull, "bear": bear, "option_score": round(bull - bear, 2), "score": round(bull - bear, 2), "confidence": round(min(100, abs(bull - bear) * evidence / len(categories)), 2), "category_scores": {name: {"bull_score": value[0], "bear_score": value[1]} for name, value in categories.items()}, "support": data.get("support"), "resistance": data.get("resistance"), "max_pain": data.get("max_pain"), "PCR": self._number(data, "PCR", "pcr"), "reasons": [reason for _, _, reasons in categories.values() for reason in reasons]}


def option_score(symbol: str = "NIFTY", option_data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return OptionScoreEngine().option_score(chain=option_data, symbol=symbol)

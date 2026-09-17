"""Immutable, fail-closed authority for a canonical directional policy."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping


_IDENTITIES = {("NIFTY", "NSE"), ("NIFTY", "NFO"), ("SENSEX", "BSE"), ("SENSEX", "BFO")}
_DIRECTIONS = {"BULLISH", "BEARISH", "NEUTRAL", "UNAVAILABLE"}
_DECISIONS = {"TRADE", "NO_TRADE", "WAIT", "UNAVAILABLE"}


def _text(value: str, name: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _score(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 100.0:
        raise ValueError(f"{name} must be a finite score in [0, 100]")
    return value


def _unique_tuple(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
    normalised = tuple(_text(value, name) for value in values)
    if len(normalised) != len(set(normalised)):
        raise ValueError(f"{name} contains duplicate values")
    return normalised


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    return value


@dataclass(frozen=True, slots=True)
class CanonicalDirectionalPolicyV1:
    """A single typed policy decision; it cannot be mutated into an executable one."""

    policy_id: str
    symbol: str
    exchange: str
    evaluated_at: datetime
    direction: str
    decision: str
    agreement_strength: float
    evidence_strength: float
    confidence: float
    score: float
    supporting_families: tuple[str, ...] = ()
    opposing_families: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    entry_restrictions: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    invalidation_reasons: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    policy_version: str = "canonical-directional-policy-v1"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    execution_enabled: bool = False

    def __post_init__(self) -> None:
        symbol = _text(self.symbol, "symbol").upper()
        exchange = _text(self.exchange, "exchange").upper()
        if (symbol, exchange) not in _IDENTITIES:
            raise ValueError("unsupported symbol/exchange identity")
        direction = _text(self.direction, "direction").upper()
        decision = _text(self.decision, "decision").upper()
        if direction not in _DIRECTIONS or decision not in _DECISIONS:
            raise ValueError("unsupported direction or decision")
        if self.execution_mode != "PAPER" or self.execution_enabled:
            raise ValueError("canonical directional policy is PAPER-only and non-executable")
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        object.__setattr__(self, "policy_version", _text(self.policy_version, "policy_version"))
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "decision", decision)
        for name in ("agreement_strength", "evidence_strength", "confidence", "score"):
            object.__setattr__(self, name, _score(getattr(self, name), name))
        for name in ("supporting_families", "opposing_families", "blockers", "warnings", "contradictions", "entry_restrictions", "reasons", "invalidation_reasons", "source_ids"):
            object.__setattr__(self, name, _unique_tuple(getattr(self, name), name))
        if set(self.supporting_families) & set(self.opposing_families):
            raise ValueError("a family cannot both support and oppose the policy")
        if direction == "UNAVAILABLE" and decision == "TRADE":
            raise ValueError("unavailable policy cannot permit trade")
        if decision == "TRADE" and (direction not in {"BULLISH", "BEARISH"} or self.blockers or self.entry_restrictions):
            raise ValueError("trade requires directional policy with no blocker or restriction")
        object.__setattr__(self, "metadata", _freeze(self.metadata))

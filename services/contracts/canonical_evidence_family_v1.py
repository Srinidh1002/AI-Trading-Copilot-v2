"""Typed, immutable evidence-family contributions for canonical policy evaluation."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Any
from .canonical_directional_policy_v1 import _aware, _freeze, _score, _unique_tuple

FAMILIES = frozenset({"TECHNICAL", "STRUCTURE", "VOLUME", "VOLATILITY", "DERIVATIVES", "BROADER_MARKET", "EXTERNAL_CONTEXT", "REGIME", "CONTRACT_QUALITY", "RISK"})
ROLES = frozenset({"DIRECTIONAL", "CONFIRMATION", "CONTRADICTION", "ENTRY_RESTRICTION", "QUALITY_GATE", "CONTRACT_SELECTION", "RISK_GATE", "INFORMATIONAL"})
STATUSES = frozenset({"AVAILABLE", "UNAVAILABLE", "BLOCKED", "NEUTRAL"})
DIRECTIONS = frozenset({"BULLISH", "BEARISH", "NEUTRAL", "UNAVAILABLE"})

@dataclass(frozen=True, slots=True)
class CanonicalEvidenceFamilyContributionV1:
    family: str; role: str; status: str; direction: str; strength: float; quality: float; observed_at: datetime
    evidence_ids: tuple[str, ...] = (); reasons: tuple[str, ...] = (); diagnostics: Mapping[str, Any] = field(default_factory=dict); provenance_ids: tuple[str, ...] = ()
    def __post_init__(self) -> None:
        family, role, status, direction = (str(getattr(self, name)).strip().upper() for name in ("family", "role", "status", "direction"))
        if family not in FAMILIES or role not in ROLES or status not in STATUSES or direction not in DIRECTIONS: raise ValueError("unsupported family, role, status, or direction")
        if role == "INFORMATIONAL" and direction not in {"NEUTRAL", "UNAVAILABLE"}: raise ValueError("informational evidence cannot supply direction")
        if status == "UNAVAILABLE" and (direction != "UNAVAILABLE" or self.strength != 0): raise ValueError("unavailable evidence cannot claim positive directional strength")
        if role in {"ENTRY_RESTRICTION", "QUALITY_GATE", "CONTRACT_SELECTION", "RISK_GATE"} and direction not in {"NEUTRAL", "UNAVAILABLE"}: raise ValueError("gate and restriction evidence is separate from direction")
        object.__setattr__(self, "family", family); object.__setattr__(self, "role", role); object.__setattr__(self, "status", status); object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "strength", _score(self.strength, "strength")); object.__setattr__(self, "quality", _score(self.quality, "quality")); object.__setattr__(self, "observed_at", _aware(self.observed_at, "observed_at"))
        for name in ("evidence_ids", "reasons", "provenance_ids"): object.__setattr__(self, name, _unique_tuple(getattr(self, name), name))
        object.__setattr__(self, "diagnostics", _freeze(self.diagnostics))

@dataclass(frozen=True, slots=True)
class CanonicalEvidenceFamilySetV1:
    contributions: tuple[CanonicalEvidenceFamilyContributionV1, ...]
    def __post_init__(self) -> None:
        if not isinstance(self.contributions, tuple) or not self.contributions: raise ValueError("contributions must be a non-empty immutable tuple")
        if not all(isinstance(item, CanonicalEvidenceFamilyContributionV1) for item in self.contributions): raise TypeError("contributions must be canonical family contributions")
        families = tuple(item.family for item in self.contributions)
        if len(families) != len(set(families)): raise ValueError("one contribution per evidence family is required")

"""Versioned, immutable constituent universe contract for X2.

This module replaces the hardcoded fallback behaviour of
``src/index_weights.py`` with an explicit, dated, provenance-carrying
contract. X2 never treats the legacy fallback weights as authoritative.

Rules enforced here:

* Weight units are explicit (FRACTION or PERCENT). Mixed units and
  implicit renormalisation are rejected.
* Weights are positive finite. A missing weight is not silently
  replaced with zero.
* The universe is single-provider (currently FYERS only).
* Observed and expected constituent counts are tracked separately.
  A partial universe is not silently normalised to 100%.
* Every constituent carries a canonical id, a provider symbol, an
  exchange, and a per-entry weight.
* Duplicate canonical ids are rejected.
* Weight effective date must not follow the observation date.
* Deterministic canonical JSON and SHA-256 identity.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any

from services.core.five_market_universe_v2 import get_target_market


class X2ConstituentError(ValueError):
    """Constituent universe contract failed closed."""


class WeightUnitV1(StrEnum):
    FRACTION = "FRACTION"
    PERCENT = "PERCENT"


CONSTITUENT_UNIVERSE_SCHEMA_V1 = "X2_CONSTITUENT_UNIVERSE_V1"

INDEX_SYMBOLS_V1 = frozenset({"NIFTY", "SENSEX"})
PROVIDERS_V1 = frozenset({"FYERS"})


def _text(name: str, value: object, *, upper: bool = False) -> str:
    if not isinstance(value, str):
        raise X2ConstituentError(f"{name} must be a string.")
    v = value.strip()
    if not v:
        raise X2ConstituentError(f"{name} must be non-empty.")
    return v.upper() if upper else v


def _aware(name: str, value: object) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise X2ConstituentError(
            f"{name} must be a timezone-aware datetime."
        )
    return value


def _positive_finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise X2ConstituentError(f"{name} must be numeric.")
    f = float(value)
    if not math.isfinite(f) or f <= 0:
        raise X2ConstituentError(
            f"{name} must be finite and positive."
        )
    return f


def _nonneg_int(name: str, value: object) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise X2ConstituentError(
            f"{name} must be a non-negative integer."
        )
    return value


def _messages(name: str, values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise X2ConstituentError(f"{name} must be a tuple.")
    out = tuple(_text(f"{name} item", v) for v in values)
    if len(set(out)) != len(out):
        raise X2ConstituentError(
            f"{name} must not contain duplicates."
        )
    return out


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise X2ConstituentError(
            "payload is not canonical-JSON compatible."
        ) from exc


@dataclass(frozen=True, slots=True)
class ConstituentEntryV1:
    canonical_constituent_id: str
    provider_symbol: str
    exchange: str
    weight: float
    sector: str | None = None

    def __post_init__(self) -> None:
        _text(
            "canonical_constituent_id",
            self.canonical_constituent_id,
        )
        _text("provider_symbol", self.provider_symbol)
        exchange = _text("exchange", self.exchange, upper=True)
        object.__setattr__(self, "exchange", exchange)
        _positive_finite("weight", self.weight)
        if self.sector is not None:
            object.__setattr__(
                self, "sector", _text("sector", self.sector)
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_constituent_id": self.canonical_constituent_id,
            "provider_symbol": self.provider_symbol,
            "exchange": self.exchange,
            "weight": float(self.weight),
            "sector": self.sector,
        }


@dataclass(frozen=True, slots=True)
class ConstituentUniverseV1:
    universe_id: str
    universe_version: str
    index_symbol: str
    index_exchange: str
    provider: str
    weight_unit: WeightUnitV1
    weight_effective_date: date
    observation_date: date
    observed_at: datetime
    source_id: str
    source_label: str
    constituents: tuple[ConstituentEntryV1, ...]
    expected_constituent_count: int
    is_partial: bool = False
    missing_reason: str | None = None
    warnings: tuple[str, ...] = ()
    schema_version: str = CONSTITUENT_UNIVERSE_SCHEMA_V1

    def __post_init__(self) -> None:
        _text("universe_id", self.universe_id)
        _text("universe_version", self.universe_version)
        index_symbol = _text(
            "index_symbol", self.index_symbol, upper=True
        )
        index_exchange = _text(
            "index_exchange", self.index_exchange, upper=True
        )
        provider = _text("provider", self.provider, upper=True)
        source_id = _text("source_id", self.source_id)
        source_label = _text("source_label", self.source_label)

        if index_symbol not in INDEX_SYMBOLS_V1:
            raise X2ConstituentError(
                f"unsupported X2 index: {index_symbol!r}"
            )
        if provider not in PROVIDERS_V1:
            raise X2ConstituentError(
                f"unsupported X2 provider: {provider!r}"
            )
        market = get_target_market(index_symbol)
        if market.market_type != "INDEX":
            raise X2ConstituentError(
                f"{index_symbol} is not an INDEX market."
            )
        if market.underlying_exchange != index_exchange:
            raise X2ConstituentError(
                "index_exchange does not match the canonical index."
            )

        if not isinstance(self.weight_unit, WeightUnitV1):
            raise X2ConstituentError(
                "weight_unit must be WeightUnitV1."
            )

        if (
            not isinstance(self.weight_effective_date, date)
            or isinstance(self.weight_effective_date, datetime)
        ):
            raise X2ConstituentError(
                "weight_effective_date must be a date."
            )
        if (
            not isinstance(self.observation_date, date)
            or isinstance(self.observation_date, datetime)
        ):
            raise X2ConstituentError(
                "observation_date must be a date."
            )
        if self.weight_effective_date > self.observation_date:
            raise X2ConstituentError(
                "weight_effective_date follows observation_date."
            )

        object.__setattr__(
            self, "observed_at", _aware("observed_at", self.observed_at)
        )

        if not isinstance(self.constituents, tuple):
            raise X2ConstituentError(
                "constituents must be a tuple."
            )
        if not self.constituents:
            raise X2ConstituentError(
                "constituents must not be empty."
            )
        seen_ids: set[str] = set()
        seen_symbols: set[tuple[str, str]] = set()
        for entry in self.constituents:
            if not isinstance(entry, ConstituentEntryV1):
                raise X2ConstituentError(
                    "constituents must be ConstituentEntryV1."
                )
            if entry.canonical_constituent_id in seen_ids:
                raise X2ConstituentError(
                    f"duplicate constituent id: "
                    f"{entry.canonical_constituent_id}"
                )
            seen_ids.add(entry.canonical_constituent_id)
            key = (entry.exchange, entry.provider_symbol)
            if key in seen_symbols:
                raise X2ConstituentError(
                    f"duplicate provider symbol: "
                    f"{entry.exchange}:{entry.provider_symbol}"
                )
            seen_symbols.add(key)

        _nonneg_int(
            "expected_constituent_count",
            self.expected_constituent_count,
        )
        if self.expected_constituent_count < len(self.constituents):
            raise X2ConstituentError(
                "expected_constituent_count < observed count."
            )
        if not isinstance(self.is_partial, bool):
            raise X2ConstituentError(
                "is_partial must be a boolean."
            )
        if self.is_partial:
            if not self.missing_reason:
                raise X2ConstituentError(
                    "partial universe requires missing_reason."
                )
            object.__setattr__(
                self,
                "missing_reason",
                _text("missing_reason", self.missing_reason),
            )
        elif self.missing_reason is not None:
            raise X2ConstituentError(
                "complete universe cannot carry missing_reason."
            )

        object.__setattr__(self, "universe_id", self.universe_id)
        object.__setattr__(
            self, "universe_version", self.universe_version
        )
        object.__setattr__(self, "index_symbol", index_symbol)
        object.__setattr__(self, "index_exchange", index_exchange)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "source_label", source_label)
        object.__setattr__(
            self, "warnings", _messages("warnings", self.warnings)
        )

        if self.schema_version != CONSTITUENT_UNIVERSE_SCHEMA_V1:
            raise X2ConstituentError(
                "unsupported constituent universe schema."
            )

    @property
    def observed_constituent_count(self) -> int:
        return len(self.constituents)

    @property
    def coverage_ratio(self) -> float:
        if self.expected_constituent_count == 0:
            return 0.0
        return (
            self.observed_constituent_count
            / self.expected_constituent_count
        )

    @property
    def total_weight(self) -> float:
        return sum(entry.weight for entry in self.constituents)

    def weight_unit_canonical(self) -> str:
        return self.weight_unit.value

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "universe_id": self.universe_id,
            "universe_version": self.universe_version,
            "index_symbol": self.index_symbol,
            "index_exchange": self.index_exchange,
            "provider": self.provider,
            "weight_unit": self.weight_unit.value,
            "weight_effective_date": self.weight_effective_date.isoformat(),
            "observation_date": self.observation_date.isoformat(),
            "observed_at": self.observed_at.isoformat(),
            "source_id": self.source_id,
            "source_label": self.source_label,
            "expected_constituent_count": self.expected_constituent_count,
            "is_partial": self.is_partial,
            "missing_reason": self.missing_reason,
            "warnings": list(self.warnings),
            "constituents": [
                entry.to_dict() for entry in self.constituents
            ],
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_payload())

    @property
    def universe_sha256(self) -> str:
        return sha256(
            self.canonical_json().encode("utf-8")
        ).hexdigest()


def build_constituent_universe_v1(
    *,
    universe_id: str,
    universe_version: str,
    index_symbol: str,
    provider: str,
    weight_unit: WeightUnitV1,
    weight_effective_date: date,
    observation_date: date,
    observed_at: datetime,
    source_id: str,
    source_label: str,
    constituents: Mapping[str, Any] | tuple[Mapping[str, Any], ...],
    expected_constituent_count: int,
    is_partial: bool = False,
    missing_reason: str | None = None,
    warnings: tuple[str, ...] = (),
) -> ConstituentUniverseV1:
    """Build a constituent universe from raw entries.

    ``constituents`` may be a sequence of mappings or a single mapping
    of ``canonical_id -> entry``. Iteration is normalised to a
    deterministic sorted tuple before constructing the immutable
    contract, so caller iteration order cannot change the resulting
    SHA-256.
    """
    if isinstance(constituents, Mapping):
        raw_entries = list(constituents.values())
    else:
        raw_entries = list(constituents)

    parsed: list[ConstituentEntryV1] = []
    for raw in raw_entries:
        if not isinstance(raw, Mapping):
            raise X2ConstituentError(
                "constituent entry must be a mapping."
            )
        parsed.append(
            ConstituentEntryV1(
                canonical_constituent_id=raw[
                    "canonical_constituent_id"
                ],
                provider_symbol=raw["provider_symbol"],
                exchange=raw["exchange"],
                weight=raw["weight"],
                sector=raw.get("sector"),
            )
        )

    parsed.sort(
        key=lambda e: (e.exchange, e.provider_symbol, e.canonical_constituent_id)
    )

    market = get_target_market(index_symbol)
    return ConstituentUniverseV1(
        universe_id=universe_id,
        universe_version=universe_version,
        index_symbol=index_symbol,
        index_exchange=market.underlying_exchange,
        provider=provider,
        weight_unit=weight_unit,
        weight_effective_date=weight_effective_date,
        observation_date=observation_date,
        observed_at=observed_at,
        source_id=source_id,
        source_label=source_label,
        constituents=tuple(parsed),
        expected_constituent_count=expected_constituent_count,
        is_partial=is_partial,
        missing_reason=missing_reason,
        warnings=warnings,
    )


__all__ = [
    "CONSTITUENT_UNIVERSE_SCHEMA_V1",
    "INDEX_SYMBOLS_V1",
    "PROVIDERS_V1",
    "ConstituentEntryV1",
    "ConstituentUniverseV1",
    "WeightUnitV1",
    "X2ConstituentError",
    "build_constituent_universe_v1",
]

"""Immutable, credential-safe option inputs captured for one PAPER market."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

_IDENTITIES = {("NIFTY", "NFO"), ("SENSEX", "BFO")}
_SECRET_WORDS = ("secret", "password", "pin", "jwt", "totp", "authorization")


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(word in str(key).lower() for key in value for word in _SECRET_WORDS):
            raise ValueError("unsafe option capture field")
        return MappingProxyType({str(key): _safe(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_safe(item) for item in value)
    if value is None or isinstance(value, (str, bool, int, float, datetime)):
        return value
    raise TypeError("unsafe option capture value")


@dataclass(frozen=True, slots=True)
class LiveOptionCaptureResultV1:
    underlying_symbol: str
    option_exchange: str
    option_chain: Mapping[str, Any]
    provider_timestamp: datetime
    evaluated_at: datetime
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "live_option_capture_result.v1"

    def __post_init__(self) -> None:
        if (self.underlying_symbol, self.option_exchange) not in _IDENTITIES:
            raise ValueError("unsupported certified option identity")
        for name, timestamp in (("provider_timestamp", self.provider_timestamp), ("evaluated_at", self.evaluated_at)):
            if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if not isinstance(self.option_chain, Mapping):
            raise TypeError("option_chain must be a mapping")
        if self.schema_version != "live_option_capture_result.v1":
            raise ValueError("unsupported schema_version")
        object.__setattr__(self, "option_chain", _safe(self.option_chain))
        object.__setattr__(self, "metadata", _safe(self.metadata))
        object.__setattr__(self, "blockers", tuple(str(item) for item in self.blockers))
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))

    @property
    def contracts(self) -> tuple[Mapping[str, Any], ...]:
        contracts = self.option_chain.get("contracts", ())
        return tuple(contracts) if isinstance(contracts, (tuple, list)) else ()

    def to_dict(self) -> dict[str, Any]:
        return {"underlying_symbol": self.underlying_symbol, "option_exchange": self.option_exchange, "contract_count": len(self.contracts), "provider_timestamp": self.provider_timestamp.isoformat(), "evaluated_at": self.evaluated_at.isoformat(), "blockers": list(self.blockers), "warnings": list(self.warnings), "metadata": dict(self.metadata), "schema_version": self.schema_version}

"""Immutable, provider-neutral technical indicator evidence."""
from __future__ import annotations

from dataclasses import dataclass
import math


_STATUSES = {"VALID", "INSUFFICIENT_HISTORY", "UNAVAILABLE", "MALFORMED", "FAILED"}
_SIGNALS = {"BULLISH", "BEARISH", "NEUTRAL", "OVERBOUGHT", "OVERSOLD", "EXPANDING", "CONTRACTING", "HIGH", "LOW", "NONE"}
_TIMEFRAMES = {"5m", "15m", "1h", "1d"}


@dataclass(frozen=True, slots=True)
class TechnicalIndicatorValueV1:
    indicator_name: str
    timeframe: str
    value: float | None
    signal: str
    status: str
    minimum_required_candles: int
    available_complete_candles: int
    parameters: tuple[tuple[str, int | float | str], ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: str = "technical_indicator_value.v1"

    def __post_init__(self) -> None:
        if (not isinstance(self.indicator_name, str) or not self.indicator_name.strip()
                or self.timeframe not in _TIMEFRAMES or self.status not in _STATUSES
                or self.signal not in _SIGNALS or self.minimum_required_candles <= 0
                or self.available_complete_candles < 0 or self.schema_version != "technical_indicator_value.v1"):
            raise ValueError("Invalid technical indicator value.")
        if self.value is not None and (isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(self.value)):
            raise ValueError("Indicator value must be finite or unavailable.")
        if self.status != "VALID" and self.value is not None:
            raise ValueError("Unavailable indicator states cannot carry a value.")
        if self.status == "VALID" and self.value is None:
            raise ValueError("A valid indicator requires a value.")
        parameters = tuple(self.parameters)
        if (len({key for key, _ in parameters}) != len(parameters)
                or any(not isinstance(key, str) or not key or isinstance(value, bool)
                       or not isinstance(value, (int, float, str))
                       or isinstance(value, float) and not math.isfinite(value)
                       for key, value in parameters)):
            raise ValueError("Invalid indicator parameters.")
        if self.status != "VALID" and not self.blockers:
            raise ValueError("Unavailable indicator state requires a blocker.")
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "blockers", tuple(self.blockers))
        object.__setattr__(self, "warnings", tuple(self.warnings))

    def to_dict(self) -> dict[str, object]:
        return {"indicator_name": self.indicator_name, "timeframe": self.timeframe,
                "value": self.value, "signal": self.signal, "status": self.status,
                "minimum_required_candles": self.minimum_required_candles,
                "available_complete_candles": self.available_complete_candles,
                "parameters": [[key, value] for key, value in self.parameters],
                "blockers": list(self.blockers), "warnings": list(self.warnings),
                "schema_version": self.schema_version}

"""Side-effect-free canonical MarketSnapshot v1 contract and legacy adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
import json
import math
from typing import Any, Mapping
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd


class SnapshotValidationError(ValueError):
    """Raised when a caller asks an invalid snapshot to be strictly valid."""


class DataStatus(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    EMPTY = "EMPTY"
    STALE = "STALE"
    INVALID = "INVALID"
    VALID = "VALID"


CANONICAL_OHLCV_COLUMNS = (
    "timestamp", "open", "high", "low", "close", "volume",
)
VALID_TIMEFRAMES = {"1m", "3m", "5m", "15m", "1h", "1d"}
VALID_INSTRUMENT_TYPES = {"INDEX", "EQUITY", "FUTURE", "OPTION"}
VALID_DATA_STATUSES = {status.value for status in DataStatus}


def _parse_datetime(value: datetime | str, timezone_name: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise SnapshotValidationError("Invalid ISO-8601 timestamp.") from exc
    if not isinstance(value, datetime):
        raise SnapshotValidationError("Timestamp must be a datetime or ISO-8601 string.")
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(timezone_name))
    return value.astimezone(ZoneInfo(timezone_name))


def _finite_number(value: Any, *, positive: bool = False) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or (positive and number <= 0):
        return None
    return number


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise SnapshotValidationError("OHLCV timestamp must be timezone-aware.")
        for name in ("open", "high", "low", "close"):
            if _finite_number(getattr(self, name), positive=True) is None:
                raise SnapshotValidationError(f"OHLCV {name} must be positive and finite.")
        if _finite_number(self.volume) is None or self.volume < 0:
            raise SnapshotValidationError("OHLCV volume must be finite and non-negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(), "open": self.open,
            "high": self.high, "low": self.low, "close": self.close,
            "volume": self.volume,
        }


@dataclass(frozen=True, slots=True)
class OHLCVSeries:
    timeframe: str
    bars: tuple[OHLCVBar, ...]

    def __post_init__(self) -> None:
        if self.timeframe not in VALID_TIMEFRAMES:
            raise SnapshotValidationError(f"Unsupported timeframe: {self.timeframe}")
        if not self.bars:
            raise SnapshotValidationError("OHLCV series cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {"timeframe": self.timeframe, "bars": [bar.to_dict() for bar in self.bars]}


def normalise_ohlcv(data: pd.DataFrame, timeframe: str, timezone_name: str = "Asia/Kolkata") -> OHLCVSeries:
    """Convert a legacy DataFrame to canonical lowercase, timezone-aware OHLCV."""
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise SnapshotValidationError("OHLCV data is unavailable or empty.")
    frame = data.copy()
    frame.columns = [str(column).lower() for column in frame.columns]
    if "timestamp" not in frame.columns:
        if isinstance(frame.index, pd.DatetimeIndex):
            frame = frame.reset_index().rename(columns={frame.index.name or "index": "timestamp"})
        else:
            raise SnapshotValidationError("OHLCV data is missing timestamp column.")
    missing = set(CANONICAL_OHLCV_COLUMNS) - set(frame.columns)
    if missing:
        raise SnapshotValidationError("OHLCV data is missing columns: " + ", ".join(sorted(missing)))
    bars: list[OHLCVBar] = []
    for record in frame.loc[:, CANONICAL_OHLCV_COLUMNS].to_dict("records"):
        bars.append(OHLCVBar(
            timestamp=_parse_datetime(record["timestamp"], timezone_name),
            open=float(record["open"]), high=float(record["high"]),
            low=float(record["low"]), close=float(record["close"]), volume=float(record["volume"]),
        ))
    return OHLCVSeries(timeframe=timeframe, bars=tuple(bars))


def to_lowercase_ohlcv(series: OHLCVSeries) -> pd.DataFrame:
    return pd.DataFrame([bar.to_dict() for bar in series.bars], columns=CANONICAL_OHLCV_COLUMNS)


def to_uppercase_ohlcv(series: OHLCVSeries) -> pd.DataFrame:
    frame = to_lowercase_ohlcv(series)
    return frame.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})


@dataclass(slots=True)
class MarketSnapshotV1:
    symbol: str
    exchange: str
    instrument_type: str
    captured_at: datetime | str
    market_timestamp: datetime | str
    ltp: float | None
    schema_version: str = "market_snapshot.v1"
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    expiry: str | None = None
    strike: float | None = None
    option_type: str | None = None
    timezone: str = "Asia/Kolkata"
    market_session: str = "UNKNOWN"
    is_market_open: bool = False
    freshness_seconds: float | None = None
    is_stale: bool = False
    previous_close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    timeframes: Mapping[str, OHLCVSeries] = field(default_factory=dict)
    option_chain_status: str = DataStatus.UNAVAILABLE
    option_chain_complete: bool | None = None
    option_chain_timestamp: datetime | str | None = None
    option_chain_data: Mapping[str, Any] | None = None
    option_chain_errors: list[str] = field(default_factory=list)
    india_vix_status: str = DataStatus.UNAVAILABLE
    india_vix_value: float | None = None
    volatility_timestamp: datetime | str | None = None
    volatility_errors: list[str] = field(default_factory=list)
    fii_dii_status: str = DataStatus.UNAVAILABLE
    fii_dii_data: Mapping[str, Any] | None = None
    institutional_timestamp: datetime | str | None = None
    institutional_errors: list[str] = field(default_factory=list)
    source_status: Mapping[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    critical_errors: list[str] = field(default_factory=list)
    missing_sources: list[str] = field(default_factory=list)
    stale_sources: list[str] = field(default_factory=list)
    validation_passed: bool = field(init=False)
    overall_status: str = field(init=False)

    def __post_init__(self) -> None:
        self.captured_at = _parse_datetime(self.captured_at, self.timezone)
        self.market_timestamp = _parse_datetime(self.market_timestamp, self.timezone)
        for attribute in ("option_chain_timestamp", "volatility_timestamp", "institutional_timestamp"):
            value = getattr(self, attribute)
            if value is not None:
                setattr(self, attribute, _parse_datetime(value, self.timezone))
        self._validate_identity()
        self._validate_price_fields()
        self._validate_derivative_identity()
        self._validate_timeframes()
        self._validate_source_statuses()
        if self.option_chain_complete is not None and not isinstance(self.option_chain_complete, bool):
            self.warnings.append("option_chain_complete must be boolean when supplied.")
            self.option_chain_complete = None
        if self.freshness_seconds is None:
            self.freshness_seconds = self.calculate_freshness(self.captured_at)
        if self.freshness_seconds < 0:
            self.critical_errors.append("Market timestamp is after capture timestamp.")
        self.is_stale = bool(self.is_stale or self.freshness_seconds > 60)
        if self.is_stale and "market" not in self.stale_sources:
            self.stale_sources.append("market")
        self.validation_passed = not self.critical_errors
        self.overall_status = (
            DataStatus.INVALID if self.critical_errors else
            DataStatus.STALE if self.is_stale else DataStatus.VALID
        )

    def _validate_identity(self) -> None:
        if self.schema_version != "market_snapshot.v1":
            self.critical_errors.append("Unsupported schema version.")
        if not isinstance(self.snapshot_id, str) or not self.snapshot_id.strip():
            self.critical_errors.append("Snapshot id is required.")
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            self.critical_errors.append("Symbol is required.")
        if not isinstance(self.exchange, str) or not self.exchange.strip():
            self.critical_errors.append("Exchange is required.")
        self.instrument_type = str(self.instrument_type).upper()
        if self.instrument_type not in VALID_INSTRUMENT_TYPES:
            self.critical_errors.append("Instrument type is invalid.")

    def _validate_price_fields(self) -> None:
        for name in ("ltp", "previous_close", "open", "high", "low", "close"):
            value = getattr(self, name)
            if value is None and name != "ltp":
                continue
            number = _finite_number(value, positive=True)
            if number is None:
                self.critical_errors.append(f"{name} must be positive and finite.")
            else:
                setattr(self, name, number)
        if self.volume is not None:
            volume = _finite_number(self.volume)
            if volume is None or volume < 0:
                self.critical_errors.append("volume must be finite and non-negative.")
            else:
                self.volume = volume

    def _validate_derivative_identity(self) -> None:
        if self.instrument_type != "OPTION":
            return
        if not self.expiry:
            self.critical_errors.append("Option expiry is required.")
        else:
            try:
                date.fromisoformat(self.expiry)
            except (TypeError, ValueError):
                self.critical_errors.append("Option expiry must be YYYY-MM-DD.")
        if _finite_number(self.strike, positive=True) is None:
            self.critical_errors.append("Option strike must be positive and finite.")
        if str(self.option_type).upper() not in {"CE", "PE"}:
            self.critical_errors.append("Option type must be CE or PE.")

    def _validate_timeframes(self) -> None:
        for name, series in self.timeframes.items():
            if name not in VALID_TIMEFRAMES or not isinstance(series, OHLCVSeries):
                self.critical_errors.append(f"Invalid timeframe payload: {name}")

    def _validate_source_statuses(self) -> None:
        """Validate source-health vocabulary without inventing positive evidence."""
        status_fields = {
            "option_chain": self.option_chain_status,
            "india_vix": self.india_vix_status,
            "fii_dii": self.fii_dii_status,
        }
        for source, status in status_fields.items():
            normalized = status.value if isinstance(status, DataStatus) else str(status).upper()
            if normalized not in VALID_DATA_STATUSES:
                self.warnings.append(f"{source} has invalid status: {status!r}.")
                normalized = DataStatus.INVALID.value
            setattr(self, f"{source}_status" if source != "india_vix" else "india_vix_status", normalized)
            if normalized == DataStatus.UNAVAILABLE.value and source not in self.missing_sources:
                self.missing_sources.append(source)
            if normalized == DataStatus.STALE.value and source not in self.stale_sources:
                self.stale_sources.append(source)
        self.option_chain_status = str(self.option_chain_status).upper()
        self.fii_dii_status = str(self.fii_dii_status).upper()
        for source, status in self.source_status.items():
            normalized = status.value if isinstance(status, DataStatus) else str(status).upper()
            if normalized not in VALID_DATA_STATUSES:
                self.warnings.append(f"{source} has invalid source status: {status!r}.")

    def calculate_freshness(self, reference_time: datetime | str) -> float:
        reference = _parse_datetime(reference_time, self.timezone)
        return round((reference - self.market_timestamp).total_seconds(), 6)

    @property
    def option_chain_available(self) -> bool:
        return self.option_chain_status in {DataStatus.VALID.value, DataStatus.STALE.value}

    @property
    def india_vix_available(self) -> bool:
        return self.india_vix_status in {DataStatus.VALID.value, DataStatus.STALE.value}

    @property
    def fii_dii_available(self) -> bool:
        return self.fii_dii_status in {DataStatus.VALID.value, DataStatus.STALE.value}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version, "snapshot_id": self.snapshot_id,
            "symbol": self.symbol, "exchange": self.exchange,
            "instrument_type": self.instrument_type, "expiry": self.expiry,
            "strike": self.strike, "option_type": self.option_type,
            "captured_at": self.captured_at.isoformat(), "market_timestamp": self.market_timestamp.isoformat(),
            "timezone": self.timezone, "market_session": self.market_session,
            "is_market_open": self.is_market_open, "freshness_seconds": self.freshness_seconds,
            "is_stale": self.is_stale, "ltp": self.ltp, "previous_close": self.previous_close,
            "open": self.open, "high": self.high, "low": self.low, "close": self.close,
            "volume": self.volume,
            "timeframes": {name: series.to_dict() for name, series in sorted(self.timeframes.items())},
            "option_chain": {"status": self.option_chain_status, "available": self.option_chain_available, "complete": self.option_chain_complete, "timestamp": self._timestamp_value(self.option_chain_timestamp), "data": self.option_chain_data, "errors": list(self.option_chain_errors)},
            "volatility": {"status": self.india_vix_status, "available": self.india_vix_available, "india_vix": self.india_vix_value, "timestamp": self._timestamp_value(self.volatility_timestamp), "errors": list(self.volatility_errors)},
            "institutional": {"status": self.fii_dii_status, "available": self.fii_dii_available, "data": self.fii_dii_data, "timestamp": self._timestamp_value(self.institutional_timestamp), "errors": list(self.institutional_errors)},
            "data_health": {"overall_status": self.overall_status, "critical_errors": list(self.critical_errors), "warnings": list(self.warnings), "missing_sources": list(self.missing_sources), "stale_sources": list(self.stale_sources), "source_status": dict(sorted(self.source_status.items())), "validation_passed": self.validation_passed},
        }

    @staticmethod
    def _timestamp_value(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MarketSnapshotV1":
        frames = {
            name: OHLCVSeries(name, tuple(OHLCVBar(
                timestamp=_parse_datetime(bar["timestamp"], payload.get("timezone", "Asia/Kolkata")),
                open=float(bar["open"]), high=float(bar["high"]), low=float(bar["low"]), close=float(bar["close"]), volume=float(bar["volume"]),
            ) for bar in series["bars"]))
            for name, series in payload.get("timeframes", {}).items()
        }
        health = payload.get("data_health", {})
        option = payload.get("option_chain", {})
        volatility = payload.get("volatility", {})
        institutional = payload.get("institutional", {})
        return cls(symbol=payload.get("symbol", ""), exchange=payload.get("exchange", ""), instrument_type=payload.get("instrument_type", ""), captured_at=payload["captured_at"], market_timestamp=payload["market_timestamp"], ltp=payload.get("ltp"), schema_version=payload.get("schema_version", "market_snapshot.v1"), snapshot_id=payload.get("snapshot_id", str(uuid4())), expiry=payload.get("expiry"), strike=payload.get("strike"), option_type=payload.get("option_type"), timezone=payload.get("timezone", "Asia/Kolkata"), market_session=payload.get("market_session", "UNKNOWN"), is_market_open=payload.get("is_market_open", False), freshness_seconds=payload.get("freshness_seconds"), is_stale=payload.get("is_stale", False), previous_close=payload.get("previous_close"), open=payload.get("open"), high=payload.get("high"), low=payload.get("low"), close=payload.get("close"), volume=payload.get("volume"), timeframes=frames, option_chain_status=option.get("status", DataStatus.UNAVAILABLE), option_chain_complete=option.get("complete"), option_chain_timestamp=option.get("timestamp"), option_chain_data=option.get("data"), option_chain_errors=option.get("errors", []), india_vix_status=volatility.get("status", DataStatus.UNAVAILABLE), india_vix_value=volatility.get("india_vix"), volatility_timestamp=volatility.get("timestamp"), volatility_errors=volatility.get("errors", []), fii_dii_status=institutional.get("status", DataStatus.UNAVAILABLE), fii_dii_data=institutional.get("data"), institutional_timestamp=institutional.get("timestamp"), institutional_errors=institutional.get("errors", []), source_status=health.get("source_status", {}), warnings=health.get("warnings", []), critical_errors=health.get("critical_errors", []), missing_sources=health.get("missing_sources", []), stale_sources=health.get("stale_sources", []))


def _option_status(value: Any) -> str:
    if value is None:
        return DataStatus.UNAVAILABLE
    if isinstance(value, Mapping) and not value:
        return DataStatus.EMPTY
    text = str(value.get("Status", "")).upper() if isinstance(value, Mapping) else ""
    return DataStatus.INVALID if text in {"FAILED", "ERROR"} else DataStatus.VALID


def _from_legacy(data: Mapping[str, Any], *, source: str, history_key: str, timestamp_key: str, reference_time: datetime | str | None = None) -> MarketSnapshotV1:
    warnings: list[str] = []
    frames: dict[str, OHLCVSeries] = {}
    history = data.get(history_key)
    if history is not None:
        try:
            frames["5m"] = normalise_ohlcv(history, "5m")
        except SnapshotValidationError as exc:
            warnings.append(f"Legacy {source} OHLCV was not mapped: {exc}")
    captured = reference_time or datetime.now(ZoneInfo("Asia/Kolkata"))
    market_timestamp = data.get(timestamp_key) or captured
    known = {"symbol", history_key, "ltp", "open", "high", "low", "close", "volume", timestamp_key, "market_status", "option_analysis", "refresh_time", "indicators", "analysis", "decision", "risk", "smart_money", "multi_timeframe"}
    unmapped = sorted(set(data) - known)
    if unmapped:
        warnings.append("Unmapped legacy fields: " + ", ".join(unmapped))
    status = str(data.get("market_status", "UNKNOWN")).upper()
    return MarketSnapshotV1(symbol=data.get("symbol", ""), exchange="NSE", instrument_type="INDEX", captured_at=captured, market_timestamp=market_timestamp, ltp=data.get("ltp"), open=data.get("open"), high=data.get("high"), low=data.get("low"), close=data.get("close"), volume=data.get("volume"), timeframes=frames, market_session=status, is_market_open=status == "OPEN", option_chain_status=_option_status(data.get("option_analysis")), option_chain_data=data.get("option_analysis"), warnings=warnings, source_status={source: DataStatus.VALID if frames else DataStatus.INVALID})


def from_dashboard_snapshot(data: Mapping[str, Any], reference_time: datetime | str | None = None) -> MarketSnapshotV1:
    return _from_legacy(data, source="dashboard", history_key="history", timestamp_key="timestamp", reference_time=reference_time)


def from_core_snapshot(data: Mapping[str, Any], reference_time: datetime | str | None = None) -> MarketSnapshotV1:
    return _from_legacy(data, source="core", history_key="history", timestamp_key="candle_time", reference_time=reference_time)


def from_live_analysis_inputs(*, symbol: str, exchange: str, market_timestamp: datetime | str, ltp: float | None, timeframes: Mapping[str, pd.DataFrame] | None = None, reference_time: datetime | str | None = None, **kwargs: Any) -> MarketSnapshotV1:
    warnings: list[str] = []
    normalised: dict[str, OHLCVSeries] = {}
    for name, frame in (timeframes or {}).items():
        try:
            normalised[name] = normalise_ohlcv(frame, name)
        except SnapshotValidationError as exc:
            warnings.append(f"{name} OHLCV unavailable: {exc}")
    return MarketSnapshotV1(symbol=symbol, exchange=exchange, instrument_type=kwargs.pop("instrument_type", "INDEX"), captured_at=reference_time or market_timestamp, market_timestamp=market_timestamp, ltp=ltp, timeframes=normalised, warnings=warnings, **kwargs)


def to_legacy_dashboard_dict(snapshot: MarketSnapshotV1) -> dict[str, Any]:
    history = to_lowercase_ohlcv(next(iter(snapshot.timeframes.values()))) if snapshot.timeframes else pd.DataFrame(columns=CANONICAL_OHLCV_COLUMNS)
    return {"symbol": snapshot.symbol, "history": history, "ltp": snapshot.ltp, "open": snapshot.open, "high": snapshot.high, "low": snapshot.low, "close": snapshot.close, "volume": snapshot.volume, "timestamp": snapshot.market_timestamp.isoformat(), "refresh_time": snapshot.captured_at.strftime("%H:%M:%S"), "market_status": "OPEN" if snapshot.is_market_open else "CLOSED", "option_analysis": snapshot.option_chain_data or {}, "snapshot_v1_warnings": list(snapshot.warnings) + list(snapshot.critical_errors)}

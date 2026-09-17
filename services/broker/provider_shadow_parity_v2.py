"""Read-only provider shadow/parity comparison utilities.

FYERS remains authoritative PRIMARY. Shadow observations are diagnostic only:
this module never returns a shadow value as a substitute for primary data and
contains no provider fallback or order capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping, Sequence


class ProviderShadowParityError(RuntimeError):
    """Invalid parity evidence or comparison input."""


@dataclass(frozen=True, slots=True)
class ShadowParityThresholdsV2:
    quote_ltp_bps: float = 25.0
    bid_ask_bps: float = 35.0
    oi_percent: float = 10.0
    volume_percent: float = 20.0
    candle_price_bps: float = 35.0
    candle_volume_percent: float = 25.0
    timestamp_lag_seconds: float = 10.0
    minimum_chain_coverage: float = 0.80

    def __post_init__(self) -> None:
        numeric = (
            self.quote_ltp_bps,
            self.bid_ask_bps,
            self.oi_percent,
            self.volume_percent,
            self.candle_price_bps,
            self.candle_volume_percent,
            self.timestamp_lag_seconds,
        )
        if any((not isfinite(v) or v < 0) for v in numeric):
            raise ValueError("Parity tolerances must be finite and non-negative.")
        if not (0 < self.minimum_chain_coverage <= 1):
            raise ValueError("minimum_chain_coverage must be in (0, 1].")


@dataclass(frozen=True, slots=True)
class ProviderParityMetricV2:
    field: str
    primary_value: float | None
    shadow_value: float | None
    divergence: float | None
    unit: str
    tolerance: float | None
    within_tolerance: bool | None


@dataclass(frozen=True, slots=True)
class ProviderParityReportV2:
    market_symbol: str
    data_kind: str
    primary_provider: str
    shadow_provider: str
    status: str
    metrics: tuple[ProviderParityMetricV2, ...]
    compared_at: datetime
    evidence_complete: bool
    warnings: tuple[str, ...] = ()
    schema_version: str = "provider_parity_report.v2"

    def __post_init__(self) -> None:
        if self.primary_provider != "FYERS":
            raise ValueError("FYERS must remain the authoritative primary provider.")
        if self.shadow_provider != "ANGEL_SMARTAPI":
            raise ValueError("Angel must remain the configured shadow provider.")
        if self.status not in {
            "MATCH",
            "DIVERGED",
            "INSUFFICIENT_EVIDENCE",
            "SHADOW_UNAVAILABLE",
        }:
            raise ValueError("Invalid parity status.")
        if self.compared_at.tzinfo is None or self.compared_at.utcoffset() is None:
            raise ValueError("compared_at must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class AngelShadowIdentityV2:
    market_symbol: str
    exchange: str
    tradingsymbol: str
    symboltoken: str

    def __post_init__(self) -> None:
        for name in ("market_symbol", "exchange", "tradingsymbol", "symboltoken"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _as_utc(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                parsed = None
            if parsed is not None and parsed.tzinfo is not None and parsed.utcoffset() is not None:
                return parsed.astimezone(timezone.utc)
    number = _number(value)
    if number is not None:
        if abs(number) >= 100_000_000_000:
            number /= 1000.0
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    return None


def _bps(primary: float | None, shadow: float | None) -> float | None:
    if primary is None or shadow is None or primary <= 0:
        return None
    return abs(shadow - primary) / primary * 10_000.0


def _percent(primary: float | None, shadow: float | None) -> float | None:
    if primary is None or shadow is None or primary == 0:
        return None
    return abs(shadow - primary) / abs(primary) * 100.0


def _metric(field: str, primary, shadow, *, unit: str, tolerance: float, divergence_fn) -> ProviderParityMetricV2:
    p = _number(primary)
    s = _number(shadow)
    divergence = divergence_fn(p, s)
    return ProviderParityMetricV2(
        field=field,
        primary_value=p,
        shadow_value=s,
        divergence=divergence,
        unit=unit,
        tolerance=tolerance,
        within_tolerance=(None if divergence is None else divergence <= tolerance),
    )


def _status(metrics: Sequence[ProviderParityMetricV2], *, required_fields: Sequence[str]) -> tuple[str, bool]:
    by_name = {metric.field: metric for metric in metrics}
    complete = all(
        name in by_name and by_name[name].within_tolerance is not None
        for name in required_fields
    )
    if not complete:
        return "INSUFFICIENT_EVIDENCE", False
    return (
        "DIVERGED"
        if any(metric.within_tolerance is False for metric in metrics if metric.within_tolerance is not None)
        else "MATCH",
        True,
    )


class ProviderShadowParityEngineV2:
    """Compare FYERS primary observations with Angel shadow observations."""

    def __init__(self, thresholds: ShadowParityThresholdsV2 | None = None, *, clock=None) -> None:
        self.thresholds = thresholds or ShadowParityThresholdsV2()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ProviderShadowParityError("clock must return timezone-aware datetime")
        return now.astimezone(timezone.utc)

    def _report(self, market_symbol: str, data_kind: str, metrics, required, warnings=()):
        status, complete = _status(metrics, required_fields=required)
        return ProviderParityReportV2(
            market_symbol=str(market_symbol).upper(),
            data_kind=data_kind,
            primary_provider="FYERS",
            shadow_provider="ANGEL_SMARTAPI",
            status=status,
            metrics=tuple(metrics),
            compared_at=self._now(),
            evidence_complete=complete,
            warnings=tuple(warnings),
        )

    def shadow_unavailable(self, market_symbol: str, data_kind: str, reason: str) -> ProviderParityReportV2:
        return ProviderParityReportV2(
            market_symbol=str(market_symbol).upper(),
            data_kind=str(data_kind).upper(),
            primary_provider="FYERS",
            shadow_provider="ANGEL_SMARTAPI",
            status="SHADOW_UNAVAILABLE",
            metrics=(),
            compared_at=self._now(),
            evidence_complete=False,
            warnings=(str(reason)[:200],),
        )

    def compare_quote(self, market_symbol: str, primary: Mapping[str, Any], shadow: Mapping[str, Any]) -> ProviderParityReportV2:
        t = self.thresholds
        metrics = [
            _metric("last_price", primary.get("last_price"), shadow.get("last_price"), unit="bps", tolerance=t.quote_ltp_bps, divergence_fn=_bps),
            _metric("bid_price", primary.get("bid_price"), shadow.get("bid_price"), unit="bps", tolerance=t.bid_ask_bps, divergence_fn=_bps),
            _metric("ask_price", primary.get("ask_price"), shadow.get("ask_price"), unit="bps", tolerance=t.bid_ask_bps, divergence_fn=_bps),
        ]
        p_ts = _as_utc(primary.get("provider_timestamp") or primary.get("timestamp") or primary.get("ts"))
        s_ts = _as_utc(shadow.get("provider_timestamp") or shadow.get("timestamp") or shadow.get("ts"))
        lag = None if p_ts is None or s_ts is None else abs((s_ts - p_ts).total_seconds())
        metrics.append(ProviderParityMetricV2(
            field="timestamp_lag",
            primary_value=None if p_ts is None else p_ts.timestamp(),
            shadow_value=None if s_ts is None else s_ts.timestamp(),
            divergence=lag,
            unit="seconds",
            tolerance=t.timestamp_lag_seconds,
            within_tolerance=(None if lag is None else lag <= t.timestamp_lag_seconds),
        ))
        return self._report(market_symbol, "QUOTE", metrics, required=("last_price",))

    def compare_depth(self, market_symbol: str, primary: Mapping[str, Any], shadow: Mapping[str, Any]) -> ProviderParityReportV2:
        t = self.thresholds
        metrics = [
            _metric("bid_price", primary.get("bid_price"), shadow.get("bid_price"), unit="bps", tolerance=t.bid_ask_bps, divergence_fn=_bps),
            _metric("ask_price", primary.get("ask_price"), shadow.get("ask_price"), unit="bps", tolerance=t.bid_ask_bps, divergence_fn=_bps),
            _metric("open_interest", primary.get("open_interest"), shadow.get("open_interest"), unit="percent", tolerance=t.oi_percent, divergence_fn=_percent),
            _metric("volume", primary.get("volume"), shadow.get("volume"), unit="percent", tolerance=t.volume_percent, divergence_fn=_percent),
        ]
        return self._report(market_symbol, "DEPTH", metrics, required=("bid_price", "ask_price"))

    def compare_candles(self, market_symbol: str, primary_rows: Sequence[Mapping[str, Any]], shadow_rows: Sequence[Mapping[str, Any]]) -> ProviderParityReportV2:
        t = self.thresholds

        def keyed(rows):
            result = {}
            for row in rows:
                ts = _as_utc(row.get("timestamp"))
                if ts is not None:
                    result[ts] = row
            return result

        p = keyed(primary_rows)
        s = keyed(shadow_rows)
        common = sorted(set(p) & set(s))
        metrics = []
        warnings = []
        if not common:
            warnings.append("NO_ALIGNED_CANDLES")
        for field in ("open", "high", "low", "close"):
            divergences = [_bps(_number(p[ts].get(field)), _number(s[ts].get(field))) for ts in common]
            divergences = [v for v in divergences if v is not None]
            worst = max(divergences) if divergences else None
            metrics.append(ProviderParityMetricV2(
                field=f"candle_{field}", primary_value=None, shadow_value=None,
                divergence=worst, unit="bps", tolerance=t.candle_price_bps,
                within_tolerance=(None if worst is None else worst <= t.candle_price_bps),
            ))
        volume_div = [_percent(_number(p[ts].get("volume")), _number(s[ts].get("volume"))) for ts in common]
        volume_div = [v for v in volume_div if v is not None]
        worst_volume = max(volume_div) if volume_div else None
        metrics.append(ProviderParityMetricV2(
            field="candle_volume", primary_value=None, shadow_value=None,
            divergence=worst_volume, unit="percent", tolerance=t.candle_volume_percent,
            within_tolerance=(None if worst_volume is None else worst_volume <= t.candle_volume_percent),
        ))
        metrics.append(ProviderParityMetricV2(
            field="aligned_candle_count", primary_value=float(len(p)), shadow_value=float(len(s)),
            divergence=float(len(common)), unit="count", tolerance=None,
            within_tolerance=(len(common) > 0),
        ))
        return self._report(
            market_symbol,
            "HISTORICAL",
            metrics,
            required=("candle_close", "aligned_candle_count"),
            warnings=warnings,
        )

    def compare_option_chain(self, market_symbol: str, primary_rows: Sequence[Mapping[str, Any]], shadow_rows: Sequence[Mapping[str, Any]]) -> ProviderParityReportV2:
        t = self.thresholds

        def key(row):
            expiry = row.get("expiry") or row.get("expiry_date")
            strike = _number(row.get("strike") if "strike" in row else row.get("strike_price"))
            option_type = str(row.get("option_type") or row.get("type") or "").upper()
            return (str(expiry), strike, option_type) if strike is not None and option_type in {"CE", "PE"} else None

        p = {key(row): row for row in primary_rows if key(row) is not None}
        s = {key(row): row for row in shadow_rows if key(row) is not None}
        common = set(p) & set(s)
        denominator = max(len(p), 1)
        coverage = len(common) / denominator
        metrics = [ProviderParityMetricV2(
            field="chain_coverage",
            primary_value=float(len(p)),
            shadow_value=float(len(s)),
            divergence=coverage,
            unit="ratio",
            tolerance=t.minimum_chain_coverage,
            within_tolerance=coverage >= t.minimum_chain_coverage,
        )]
        for field, unit, tolerance, fn in (
            ("ltp", "bps", t.quote_ltp_bps, _bps),
            ("bid", "bps", t.bid_ask_bps, _bps),
            ("ask", "bps", t.bid_ask_bps, _bps),
            ("oi", "percent", t.oi_percent, _percent),
            ("volume", "percent", t.volume_percent, _percent),
        ):
            values = [fn(_number(p[k].get(field)), _number(s[k].get(field))) for k in common]
            values = [v for v in values if v is not None]
            worst = max(values) if values else None
            metrics.append(ProviderParityMetricV2(
                field=f"chain_{field}", primary_value=None, shadow_value=None,
                divergence=worst, unit=unit, tolerance=tolerance,
                within_tolerance=(None if worst is None else worst <= tolerance),
            ))
        return self._report(market_symbol, "OPTION_CHAIN", metrics, required=("chain_coverage",))

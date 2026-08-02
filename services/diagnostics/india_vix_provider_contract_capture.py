"""Strictly redacted, diagnostic-only Angel India VIX contract capture."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo


STATUSES = frozenset({"CONFIRMED", "AMBIGUOUS", "INCOMPLETE", "PROVIDER_UNAVAILABLE", "REJECTED"})
SUPPORTED_NAMES = ("India VIX", "INDIA VIX")
MASTER_URL_IDENTIFIER = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
SAFE_MASTER_FIELDS = ("token", "symbol", "name", "exch_seg", "instrumenttype", "expiry", "strike", "tick_size", "lotsize")
SAFE_QUOTE_FIELDS = ("ltp", "previousClose", "open", "opn", "high", "low", "close", "tradingSymbol", "symbolToken", "exchange", "exchFeedTime", "exchangeTimestamp", "timestamp")
_SECRET_TERMS = ("api_key", "apikey", "client_secret", "password", "pin", "totp", "jwt", "refresh", "authorization", "cookie")
_ANGEL_TIMESTAMP_FORMAT = "%d-%b-%Y %H:%M:%S"
_IST = ZoneInfo("Asia/Kolkata")


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must be a tuple of non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} must not contain duplicates")
    return value


def _safe_metadata(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("safe_metadata must be a mapping")
    result: dict[str, Any] = {}
    for key, item in value.items():
        name = str(key)
        lowered = name.lower()
        if any(term in lowered for term in _SECRET_TERMS):
            raise ValueError("unsafe metadata key")
        if isinstance(item, Mapping):
            result[name] = _safe_metadata(item)
        elif isinstance(item, (tuple, list)):
            result[name] = tuple(_safe_metadata({str(index): nested})[str(index)] for index, nested in enumerate(item))
        elif item is None or isinstance(item, (str, bool, int, float)):
            result[name] = item
        else:
            raise TypeError("safe_metadata contains unsupported value")
    return MappingProxyType(dict(sorted(result.items())))


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _safe_field_names(value: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(str(key) for key in value if not any(term in str(key).lower() for term in _SECRET_TERMS)))


@dataclass(frozen=True, slots=True)
class IndiaVixMasterEvidenceV1:
    source_url_identifier: str
    fetched_at: datetime
    matching_records: tuple[Mapping[str, Any], ...]
    duplicate_count: int
    exact_match_decision: str
    status: str
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: str = "india_vix_master_evidence.v1"

    def __post_init__(self) -> None:
        if not self.source_url_identifier or self.status not in STATUSES or self.exact_match_decision not in {"EXACTLY_ONE", "ZERO", "MULTIPLE", "INVALID"} or self.duplicate_count < 0 or self.schema_version != "india_vix_master_evidence.v1":
            raise ValueError("invalid master evidence")
        object.__setattr__(self, "fetched_at", _aware(self.fetched_at, "fetched_at"))
        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))
        object.__setattr__(self, "matching_records", tuple(MappingProxyType(dict(record)) for record in self.matching_records))

    def to_dict(self) -> dict[str, Any]:
        return {"source_url_identifier": self.source_url_identifier, "fetched_at": self.fetched_at.isoformat(), "matching_records": [_plain(record) for record in self.matching_records], "duplicate_count": self.duplicate_count, "exact_match_decision": self.exact_match_decision, "status": self.status, "blockers": list(self.blockers), "warnings": list(self.warnings), "schema_version": self.schema_version}


@dataclass(frozen=True, slots=True)
class IndiaVixQuoteSchemaEvidenceV1:
    requested_mode: str
    requested_exchange: str | None
    requested_trading_symbol: str | None
    requested_symbol_token: str | None
    requested_at: datetime
    received_at: datetime | None
    top_level_fields: tuple[str, ...]
    nested_data_fields: tuple[str, ...]
    safe_values: Mapping[str, Any]
    value_types: Mapping[str, str]
    missing_fields: tuple[str, ...]
    provider_timestamp_field: str | None
    provider_timestamp_value: str | int | float | None
    parsed_provider_timestamp: datetime | None
    provider_timestamp_is_provider_issued: bool
    timestamp_age_seconds: float | None
    previous_close_field: str | None
    previous_close_semantics_proven: bool
    identity_matches_master: bool
    is_cached: bool | None
    provider_status: str | None
    status: str
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    historical_evidence: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "india_vix_quote_schema_evidence.v1"

    def __post_init__(self) -> None:
        if self.requested_mode != "FULL" or self.status not in STATUSES or self.schema_version != "india_vix_quote_schema_evidence.v1":
            raise ValueError("invalid quote evidence")
        object.__setattr__(self, "requested_at", _aware(self.requested_at, "requested_at"))
        if self.received_at is not None: object.__setattr__(self, "received_at", _aware(self.received_at, "received_at"))
        if self.parsed_provider_timestamp is not None: object.__setattr__(self, "parsed_provider_timestamp", _aware(self.parsed_provider_timestamp, "parsed_provider_timestamp"))
        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers")); object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))
        object.__setattr__(self, "safe_values", _safe_metadata(self.safe_values)); object.__setattr__(self, "value_types", _safe_metadata(self.value_types)); object.__setattr__(self, "historical_evidence", _safe_metadata(self.historical_evidence))

    def to_dict(self) -> dict[str, Any]:
        return {"requested_mode": self.requested_mode, "requested_exchange": self.requested_exchange, "requested_trading_symbol": self.requested_trading_symbol, "requested_symbol_token": self.requested_symbol_token, "requested_at": self.requested_at.isoformat(), "received_at": self.received_at.isoformat() if self.received_at else None, "top_level_fields": list(self.top_level_fields), "nested_data_fields": list(self.nested_data_fields), "safe_values": _plain(self.safe_values), "value_types": _plain(self.value_types), "missing_fields": list(self.missing_fields), "provider_timestamp_field": self.provider_timestamp_field, "provider_timestamp_value": self.provider_timestamp_value, "parsed_provider_timestamp": self.parsed_provider_timestamp.isoformat() if self.parsed_provider_timestamp else None, "provider_timestamp_is_provider_issued": self.provider_timestamp_is_provider_issued, "timestamp_age_seconds": self.timestamp_age_seconds, "previous_close_field": self.previous_close_field, "previous_close_semantics_proven": self.previous_close_semantics_proven, "identity_matches_master": self.identity_matches_master, "is_cached": self.is_cached, "provider_status": self.provider_status, "status": self.status, "blockers": list(self.blockers), "warnings": list(self.warnings), "historical_evidence": _plain(self.historical_evidence), "schema_version": self.schema_version}


@dataclass(frozen=True, slots=True)
class IndiaVixProviderContractEvidenceV1:
    evaluated_at: datetime
    master: IndiaVixMasterEvidenceV1
    quote: IndiaVixQuoteSchemaEvidenceV1 | None
    status: str
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: str = "india_vix_provider_contract_evidence.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))
        if type(self.master) is not IndiaVixMasterEvidenceV1 or self.status not in STATUSES or self.schema_version != "india_vix_provider_contract_evidence.v1": raise ValueError("invalid provider evidence")
        if self.quote is not None and type(self.quote) is not IndiaVixQuoteSchemaEvidenceV1: raise ValueError("invalid quote")
        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers")); object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))

    def to_dict(self) -> dict[str, Any]:
        return {"evaluated_at": self.evaluated_at.isoformat(), "master": self.master.to_dict(), "quote": self.quote.to_dict() if self.quote else None, "status": self.status, "blockers": list(self.blockers), "warnings": list(self.warnings), "schema_version": self.schema_version}

    def to_json(self) -> str: return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _record(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return {field: record.get(field) for field in SAFE_MASTER_FIELDS if field in record}


def collect_master_evidence(records: Sequence[Mapping[str, Any]], *, fetched_at: datetime, cached_records: Sequence[Mapping[str, Any]] = ()) -> IndiaVixMasterEvidenceV1:
    _aware(fetched_at, "fetched_at")
    matches = [record for record in records if isinstance(record, Mapping) and str(record.get("name", "")) in SUPPORTED_NAMES and str(record.get("symbol", "")) in SUPPORTED_NAMES]
    valid = [record for record in matches if str(record.get("exch_seg", "")).upper() == "NSE" and str(record.get("instrumenttype", "")).upper() == "AMXIDX"]
    blockers: list[str] = []
    if not valid: blockers.append("INDIA_VIX_MASTER_IDENTITY_NOT_FOUND")
    if len(valid) > 1: blockers.append("INDIA_VIX_MASTER_IDENTITY_AMBIGUOUS")
    if matches and not valid: blockers.append("INDIA_VIX_MASTER_IDENTITY_REJECTED")
    if len(valid) == 1:
        cached = [item for item in cached_records if isinstance(item, Mapping) and str(item.get("name", "")) in SUPPORTED_NAMES and str(item.get("symbol", "")) in SUPPORTED_NAMES]
        if cached and any(str(item.get("token")) != str(valid[0].get("token")) for item in cached): blockers.append("INDIA_VIX_CACHED_MASTER_TOKEN_MISMATCH")
    decision = "EXACTLY_ONE" if len(valid) == 1 else "ZERO" if not valid else "MULTIPLE"
    status = "CONFIRMED" if decision == "EXACTLY_ONE" and not blockers else "AMBIGUOUS" if len(valid) > 1 else "REJECTED"
    return IndiaVixMasterEvidenceV1(MASTER_URL_IDENTIFIER, fetched_at, tuple(_record(item) for item in matches), max(0, len(valid) - 1), decision, status, tuple(blockers))


def _parse_provider_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime): return _aware(value, "provider timestamp")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(float(value) / (1000 if value > 100000000000 else 1), tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return _aware(parsed, "provider timestamp")
        except ValueError:
            return datetime.strptime(value, _ANGEL_TIMESTAMP_FORMAT).replace(tzinfo=_IST)
    return None


def capture_provider_contract(*, master_fetcher: Callable[[], Sequence[Mapping[str, Any]]], market_client: object, clock: Callable[[], datetime], cached_records: Sequence[Mapping[str, Any]] = (), previous_close_semantics_proven: bool = False, inspect_historical: bool = False) -> IndiaVixProviderContractEvidenceV1:
    fetched_at = _aware(clock(), "clock")
    try: master = collect_master_evidence(master_fetcher(), fetched_at=fetched_at, cached_records=cached_records)
    except Exception as exc:
        master = IndiaVixMasterEvidenceV1(MASTER_URL_IDENTIFIER, fetched_at, (), 0, "INVALID", "PROVIDER_UNAVAILABLE", (f"INDIA_VIX_MASTER_FETCH_FAILED:{type(exc).__name__}",))
    if master.status != "CONFIRMED": return IndiaVixProviderContractEvidenceV1(_aware(clock(), "clock"), master, None, master.status, master.blockers)
    candidate = master.matching_records[0]; requested_at = _aware(clock(), "clock"); token = str(candidate["token"]); symbol = str(candidate["symbol"])
    try: raw = market_client.get_market_data("FULL", {"NSE": [token]}); received_at = _aware(clock(), "clock")
    except Exception as exc:
        quote = IndiaVixQuoteSchemaEvidenceV1("FULL", "NSE", symbol, token, requested_at, None, (), (), {}, {}, (), None, None, None, False, None, None, False, False, None, None, "PROVIDER_UNAVAILABLE", (f"INDIA_VIX_QUOTE_FAILED:{type(exc).__name__}",))
        return IndiaVixProviderContractEvidenceV1(received_at if 'received_at' in locals() else requested_at, master, quote, "PROVIDER_UNAVAILABLE", quote.blockers)
    top = _safe_field_names(raw) if isinstance(raw, Mapping) else ()
    data = raw.get("data") if isinstance(raw, Mapping) else None; fetched = data.get("fetched") if isinstance(data, Mapping) else None
    row = fetched[0] if isinstance(fetched, list) and len(fetched) == 1 and isinstance(fetched[0], Mapping) else {}
    values = {key: row[key] for key in SAFE_QUOTE_FIELDS if key in row and (row[key] is None or isinstance(row[key], (str, int, float, bool)))}
    types = {key: type(value).__name__ for key, value in values.items()}; missing = tuple(key for key in ("ltp", "tradingSymbol", "symbolToken", "exchange") if key not in values)
    timestamp_field = next((key for key in ("exchFeedTime", "exchangeTimestamp", "timestamp") if key in values), None)
    blockers = list()
    try: parsed = _parse_provider_timestamp(values[timestamp_field]) if timestamp_field else None
    except (TypeError, ValueError, OverflowError): parsed = None; blockers.append("INDIA_VIX_PROVIDER_TIMESTAMP_UNPROVEN")
    if parsed is None: blockers.append("INDIA_VIX_PROVIDER_TIMESTAMP_UNPROVEN")
    age = (received_at - parsed).total_seconds() if parsed else None
    if age is not None and (age < -5 or age > 300): blockers.append("INDIA_VIX_PROVIDER_TIMESTAMP_NOT_FRESH")
    ltp = values.get("ltp")
    if isinstance(ltp, bool) or not isinstance(ltp, (int, float)) or not math.isfinite(float(ltp)) or float(ltp) <= 0: blockers.append("INDIA_VIX_LTP_INVALID")
    previous_field = "previousClose" if "previousClose" in values else None
    previous_value = values.get(previous_field) if previous_field else None
    if previous_field is None or isinstance(previous_value, bool) or not isinstance(previous_value, (int, float)) or not math.isfinite(float(previous_value)) or float(previous_value) <= 0 or not previous_close_semantics_proven:
        blockers.append("INDIA_VIX_PREVIOUS_CLOSE_SEMANTICS_UNPROVEN")
    identity = values.get("symbolToken") == token and values.get("tradingSymbol") == symbol and str(values.get("exchange", "")).upper() == "NSE"
    if not identity: blockers.append("INDIA_VIX_QUOTE_IDENTITY_MISMATCH")
    status = "CONFIRMED" if not blockers else "INCOMPLETE"
    historical: dict[str, Any] = {"status": "NOT_REQUESTED"}
    if inspect_historical and previous_field is None:
        try:
            response = market_client.get_historical_data(exchange="NSE", symboltoken=token, interval="ONE_DAY", fromdate=(received_at - timedelta(days=7)).strftime("%Y-%m-%d %H:%M"), todate=received_at.strftime("%Y-%m-%d %H:%M"))
            historical = {"status": "SCHEMA_ONLY", "interval": "ONE_DAY", "top_level_fields": list(_safe_field_names(response)) if isinstance(response, Mapping) else []}
        except Exception as exc:
            historical = {"status": "FAILED", "error_type": type(exc).__name__}
    quote = IndiaVixQuoteSchemaEvidenceV1("FULL", "NSE", symbol, token, requested_at, received_at, top, _safe_field_names(data) if isinstance(data, Mapping) else (), values, types, missing, timestamp_field, values.get(timestamp_field) if timestamp_field else None, parsed, parsed is not None, age, previous_field, previous_close_semantics_proven, identity, None, str(raw.get("status")) if isinstance(raw, Mapping) and "status" in raw else None, status, tuple(dict.fromkeys(blockers)), (), historical)
    return IndiaVixProviderContractEvidenceV1(received_at, master, quote, status, quote.blockers)


def load_cached_master(path: Path) -> tuple[Mapping[str, Any], ...]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return tuple(item for item in value if isinstance(item, Mapping)) if isinstance(value, list) else ()
    except (OSError, ValueError): return ()

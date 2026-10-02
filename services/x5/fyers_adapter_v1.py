"""Pure FYERS native-option-chain -> X5 research capture adapter.

Consumes FyersOptionChainProviderV2.get_option_chain output, not an SDK client.
Every evidence flag, timestamp, symbol identity and unit is supplied by a
separate verified caller/capture manifest; no provider semantics are inferred.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from services.x5.chain_validation_v1 import validate_x5_chain_v1
from services.x5.contracts_v1 import (
    X5ChainCaptureV1,
    X5ChainValidationV1,
    X5ContractV1,
    X5OptionObservationV1,
    canonical_sha256,
)

IST = timezone(timedelta(hours=5, minutes=30))
_NORMALIZED_ROW_KEYS = frozenset(
    {
        "symbol",
        "strike",
        "type",
        "ltp",
        "oi",
        "oich",
        "prev_oi",
        "volume",
        "bid",
        "ask",
        "token",
        "expiry",
    }
)

_SYMBOL_PREFIX = {
    "NIFTY": "NSE:NIFTY",
    "SENSEX": "BSE:SENSEX",
    "CRUDEOILM": "MCX:CRUDEOILM",
    "GOLDM": "MCX:GOLDM",
    "NATGASMINI": "MCX:NATGASMINI",
}


@dataclass(frozen=True, slots=True)
class X5FyersAdaptedChainV1:
    capture: X5ChainCaptureV1
    validation: X5ChainValidationV1
    source_payload_sha256: str
    schema_version: str = "X5_FYERS_ADAPTED_CHAIN_V1"
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.validation.source_capture_sha256 != self.capture.sha256()
            or len(self.source_payload_sha256) != 64
            or not all(c in "0123456789abcdef" for c in self.source_payload_sha256)
            or self.schema_version != "X5_FYERS_ADAPTED_CHAIN_V1"
            or self.data_only is not True
            or any(
                (
                    self.execution_authority,
                    self.risk_authority,
                    self.position_authority,
                    self.certification_authority,
                    self.live_execution_eligible,
                )
            )
        ):
            raise ValueError(
                "Adapted research output must have valid provenance and zero authority"
            )


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _number(value: object, field: str, *, signed: bool = False) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or (value < 0 and not signed):
        raise ValueError(f"Invalid numeric FYERS field: {field}")
    return float(value)


def _expiry_matches(row_expiry: object, expected: date, provider_epoch: int) -> bool:
    # Exact provider epoch OR exact ISO date; no timestamp offset guessing.
    if isinstance(row_expiry, date) and not isinstance(row_expiry, datetime):
        return row_expiry == expected
    if type(row_expiry) is int:
        return row_expiry == provider_epoch
    if isinstance(row_expiry, str):
        return row_expiry == expected.isoformat() or row_expiry == str(provider_epoch)
    return False


def _expiry_proof(provider_result: Mapping[str, object], contract: X5ContractV1) -> int:
    if provider_result.get("provider_expiry_date") != contract.expiry.isoformat():
        raise ValueError("FYERS selected expiry does not match canonical contract")
    epoch = provider_result.get("provider_expiry_timestamp")
    if type(epoch) is not int or epoch < 1_000_000_000 or epoch >= 10_000_000_000:
        raise ValueError("Exact FYERS expiry epoch is required")
    if datetime.fromtimestamp(epoch, UTC).astimezone(IST).date() != contract.expiry:
        raise ValueError("FYERS expiry epoch and expiry date disagree in IST")
    raw = provider_result.get("expiry_data")
    if type(raw) not in (list, tuple):
        raise ValueError("FYERS expiryData must be provided")
    matches = [
        row
        for row in raw
        if isinstance(row, Mapping) and row.get("date") == contract.expiry.isoformat()
    ]
    if len(matches) != 1 or str(matches[0].get("expiry")) != str(epoch):
        raise ValueError("FYERS expiryData proof is missing, duplicate or inconsistent")
    return epoch


def adapt_fyers_option_chain_v1(
    *,
    contract: X5ContractV1,
    provider_result: Mapping[str, object],
    canonical_ids_by_symbol: Mapping[str, str],
    observed_at_by_symbol: Mapping[str, datetime],
    as_of: datetime,
    captured_at: datetime,
    session_id: str,
    capture_id: str,
    source_id: str,
    capture_verified: bool,
    expiry_verified: bool,
    timestamp_semantics_verified: bool,
    point_in_time_verified: bool,
    historical_retrieval: bool,
    oi_unit: str | None,
    oi_unit_verified: bool,
    oi_timestamp_verified: bool,
    volume_unit: str | None,
    volume_unit_verified: bool,
    volume_timestamp_verified: bool,
    premium_unit: str | None,
    premium_unit_verified: bool,
    oi_change_is_absolute_verified: bool,
    oi_change_baselines_by_symbol: Mapping[str, str] | None,
    underlying_value: float | None,
    underlying_unit: str | None,
    underlying_verified: bool,
    underlying_source_id: str | None,
    underlying_observed_at: datetime | None,
    max_age_seconds: float,
) -> X5FyersAdaptedChainV1:
    """Create one research-only X5 capture from an already retrieved native chain.

    The caller must independently verify the evidence flags and supply an exact
    canonical-option mapping from its instrument master. No network, broker,
    timestamp substitution, strike filling, IV/Greeks fabrication or order API.
    """
    if not isinstance(contract, X5ContractV1) or not isinstance(provider_result, Mapping):
        raise ValueError("Canonical X5 contract and FYERS provider result are required")
    if not _aware(as_of) or not _aware(captured_at):
        raise ValueError("As-of and capture timestamps must be aware")
    if not all(_text(x) for x in (session_id, capture_id, source_id)):
        raise ValueError("Session, capture and source identities are required")
    flags = (
        capture_verified,
        expiry_verified,
        timestamp_semantics_verified,
        point_in_time_verified,
        historical_retrieval,
        oi_unit_verified,
        oi_timestamp_verified,
        volume_unit_verified,
        volume_timestamp_verified,
        premium_unit_verified,
        oi_change_is_absolute_verified,
        underlying_verified,
    )
    if any(type(x) is not bool for x in flags):
        raise ValueError("Verification flags must be exact booleans")
    if point_in_time_verified and not (
        capture_verified
        and expiry_verified
        and timestamp_semantics_verified
        and not historical_retrieval
        and captured_at <= as_of
    ):
        raise ValueError("Point-in-time proof requires contemporaneous verified capture")
    if (
        provider_result.get("provider") != "FYERS"
        or provider_result.get("underlying_symbol") != contract.underlying_provider_symbol
    ):
        raise ValueError("FYERS underlying identity mismatch")
    if (
        provider_result.get("data_only") is not True
        or provider_result.get("live_execution_eligible") is not False
        or type(provider_result.get("request_count")) is not int
        or provider_result["request_count"] != 1
        or type(provider_result.get("per_contract_depth_requests")) is not int
        or provider_result["per_contract_depth_requests"] != 0
    ):
        raise ValueError("Only the data-only native single-chain response is accepted")
    expiry_epoch = _expiry_proof(provider_result, contract)
    rows = provider_result.get("rows")
    if type(rows) not in (list, tuple) or not rows:
        raise ValueError("Native FYERS chain must contain CE/PE rows")
    if (
        not isinstance(canonical_ids_by_symbol, Mapping)
        or not isinstance(observed_at_by_symbol, Mapping)
        or (
            oi_change_baselines_by_symbol is not None
            and not isinstance(oi_change_baselines_by_symbol, Mapping)
        )
    ):
        raise ValueError("Exact identity, timestamp and OI baseline mappings are required")
    if (
        type(max_age_seconds) not in (int, float)
        or not math.isfinite(max_age_seconds)
        or max_age_seconds <= 0
    ):
        raise ValueError("Positive finite source freshness budget required")
    if oi_unit_verified and (not _text(oi_unit) or oi_unit in ("UNKNOWN", "UNVERIFIED")):
        raise ValueError("Verified OI requires an independently proven unit")
    if volume_unit_verified and (
        not _text(volume_unit) or volume_unit in ("UNKNOWN", "UNVERIFIED")
    ):
        raise ValueError("Verified volume requires an independently proven unit")
    if premium_unit_verified and not _text(premium_unit):
        raise ValueError("Verified premium requires a proven unit")
    if oi_change_is_absolute_verified and not (
        oi_unit_verified and oi_timestamp_verified and oi_change_baselines_by_symbol
    ):
        raise ValueError("Absolute OI change needs verified units, time and comparable baselines")
    if underlying_verified:
        if not (
            _text(underlying_source_id)
            and _aware(underlying_observed_at)
            and underlying_observed_at <= as_of
            and underlying_observed_at <= captured_at
            and (as_of - underlying_observed_at).total_seconds() <= max_age_seconds
        ):
            raise ValueError("Verified underlying requires a timely independent source")
    # Preserve signed provider oich as absolute OI change ONLY after separate proof.
    observations: list[X5OptionObservationV1] = []
    symbols: set[str] = set()
    prefix = _SYMBOL_PREFIX[contract.market]
    for row in rows:
        if not isinstance(row, Mapping) or set(row) - _NORMALIZED_ROW_KEYS:
            raise ValueError("Malformed or non-normalized provider option row")
        symbol = row.get("symbol")
        side = row.get("type")
        if (
            not _text(symbol)
            or not symbol.startswith(prefix)
            or side not in ("CE", "PE")
            or not symbol.endswith(side)
        ):
            raise ValueError("Provider symbol or CE/PE identity mismatch")
        if symbol in symbols:
            raise ValueError("Duplicate provider option symbol")
        symbols.add(symbol)
        if not _expiry_matches(row.get("expiry"), contract.expiry, expiry_epoch):
            raise ValueError("Missing or mismatched option-row expiry")
        identifier = canonical_ids_by_symbol.get(symbol)
        observed = observed_at_by_symbol.get(symbol)
        if not _text(identifier) or not _aware(observed):
            raise ValueError("Missing authoritative option ID or source observation timestamp")
        if observed > as_of or observed > captured_at:
            raise ValueError("Future-dated option observation")
        strike = _number(row.get("strike"), "strike")
        if strike is None or strike <= 0:
            raise ValueError("Positive option strike required")
        oi = _number(row.get("oi"), "oi")
        volume = _number(row.get("volume"), "volume")
        change = (
            _number(row.get("oich"), "oich", signed=True)
            if oi_change_is_absolute_verified
            else None
        )
        baseline = (
            oi_change_baselines_by_symbol.get(symbol) if oi_change_is_absolute_verified else None
        )
        if oi_change_is_absolute_verified and (change is None or not _text(baseline)):
            raise ValueError("Verified absolute OI change missing comparable row or baseline")
        observations.append(
            X5OptionObservationV1(
                canonical_option_id=identifier,
                provider_symbol=symbol,
                option_type=side,
                strike=strike,
                expiry=contract.expiry,
                observed_at=observed,
                source_record_id=f"{capture_id}:{symbol}",
                ltp=_number(row.get("ltp"), "ltp"),
                bid_price=_number(row.get("bid"), "bid"),
                ask_price=_number(row.get("ask"), "ask"),
                volume=volume,
                open_interest=oi,
                oi_unit=oi_unit if oi is not None else None,
                volume_unit=volume_unit if volume is not None else None,
                change_in_open_interest=change,
                premium_unit=premium_unit,
                oi_unit_verified=oi_unit_verified and oi is not None,
                oi_timestamp_verified=oi_timestamp_verified and oi is not None,
                volume_unit_verified=volume_unit_verified and volume is not None,
                volume_timestamp_verified=volume_timestamp_verified and volume is not None,
                premium_unit_verified=premium_unit_verified
                and any(row.get(k) is not None for k in ("ltp", "bid", "ask")),
                oi_change_verified=oi_change_is_absolute_verified,
                oi_change_baseline_id=baseline,
                # Native normalizer provides neither verified IV nor Greeks.
                implied_volatility=None,
                iv_verified=False,
                greeks_verified=False,
            )
        )
    if symbols != set(canonical_ids_by_symbol) or symbols != set(observed_at_by_symbol):
        raise ValueError("Provider chain and verified identity/timestamp inventories differ")
    if oi_change_is_absolute_verified and symbols != set(oi_change_baselines_by_symbol):
        raise ValueError("OI comparison inventory differs from provider rows")
    capture = X5ChainCaptureV1(
        contract=contract,
        session_id=session_id,
        capture_id=capture_id,
        source_id=source_id,
        as_of=as_of,
        captured_at=captured_at,
        observations=tuple(observations),
        underlying_value=underlying_value,
        underlying_unit=underlying_unit,
        underlying_verified=underlying_verified,
        capture_verified=capture_verified,
        expiry_verified=expiry_verified,
        timestamp_semantics_verified=timestamp_semantics_verified,
        point_in_time_verified=point_in_time_verified,
        historical_retrieval=historical_retrieval,
    )
    validation = validate_x5_chain_v1(capture, max_age_seconds=max_age_seconds)
    payload = {
        "provider": provider_result["provider"],
        "underlying_symbol": provider_result["underlying_symbol"],
        "expiry": contract.expiry.isoformat(),
        "expiry_epoch": expiry_epoch,
        "rows": tuple(dict(row) for row in rows),
    }
    return X5FyersAdaptedChainV1(
        capture=capture,
        validation=validation,
        source_payload_sha256=canonical_sha256(payload),
    )

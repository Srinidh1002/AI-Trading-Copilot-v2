"""Pure X4 multi-timeframe futures research; no broker, network or PAPER I/O.

Composes independently verified, single-contract FYERS historical captures.
An alignment is descriptive evidence, never a trade decision or voting score.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime

from services.x4.contracts_v1 import (
    X4BasisReferenceV1,
    X4ContractV1,
    X4ResultV1,
    _aware,
    canonical_sha256,
)
from services.x4.futures_engine_v1 import analyze_futures_v1
from services.x4.fyers_adapter_v1 import _INTERVALS, X4AdaptedCandlesV1

_UP_STATES = frozenset({"LONG_BUILDUP", "SHORT_COVERING"})
_DOWN_STATES = frozenset({"SHORT_BUILDUP", "LONG_UNWINDING"})
_ALIGNMENTS = frozenset({"CONSISTENT_UP", "CONSISTENT_DOWN", "FLAT", "MIXED", "INSUFFICIENT_DATA"})


@dataclass(frozen=True, slots=True)
class X4TimeframeEvidenceV1:
    """Traceable diagnostic evidence, not separate directional votes."""

    timeframe: str
    capture_id: str
    positioning_state: str
    status: str
    available_feature_ids: tuple[str, ...]
    unavailable_feature_ids: tuple[str, ...]
    oi_change_verified: bool
    volume_change_verified: bool
    candle_vwap_estimate_available: bool
    blockers: tuple[str, ...]
    schema_version: str = "X4_TIMEFRAME_EVIDENCE_V1"
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.timeframe not in _INTERVALS
            or not self.capture_id
            or self.status not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}
            or self.schema_version != "X4_TIMEFRAME_EVIDENCE_V1"
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
            raise ValueError("Invalid or authority-bearing X4 timeframe evidence")


@dataclass(frozen=True, slots=True)
class X4MultiTimeframeResultV1:
    market: str
    instrument_id: str
    provider_symbol: str
    session_id: str
    as_of: datetime
    required_timeframes: tuple[str, ...]
    timeframe_results: tuple[X4ResultV1, ...]
    evidence: tuple[X4TimeframeEvidenceV1, ...]
    missing_timeframes: tuple[str, ...]
    alignment: str
    status: str
    blockers: tuple[str, ...]
    schema_version: str = "X4_MULTI_TIMEFRAME_RESULT_V1"
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        names = tuple(item.timeframe for item in self.timeframe_results)
        evidence_names = tuple(item.timeframe for item in self.evidence)
        if (
            not self.market
            or not self.instrument_id
            or not self.provider_symbol
            or not self.session_id
            or not _aware(self.as_of)
            or len(self.required_timeframes) < 2
            or len(set(self.required_timeframes)) != len(self.required_timeframes)
            or any(tf not in _INTERVALS for tf in self.required_timeframes)
            or names != evidence_names
            or len(set(names)) != len(names)
            or tuple(tf for tf in self.required_timeframes if tf in names) != names
            or tuple(tf for tf in self.required_timeframes if tf not in names)
            != self.missing_timeframes
            or self.alignment not in _ALIGNMENTS
            or self.status not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}
            or self.schema_version != "X4_MULTI_TIMEFRAME_RESULT_V1"
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
            raise ValueError("Invalid or authority-bearing X4 multi-timeframe result")

    def to_dict(self) -> dict[str, object]:
        """Canonical serializer shared with the existing X4 result contracts."""
        from services.x4.contracts_v1 import _encode

        return _encode(asdict(self))

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def _evidence(frame: X4ResultV1, capture_id: str) -> X4TimeframeEvidenceV1:
    available = frozenset(
        feature.feature_id for feature in frame.features if feature.status == "AVAILABLE"
    )
    return X4TimeframeEvidenceV1(
        timeframe=frame.timeframe,
        capture_id=capture_id,
        positioning_state=frame.positioning_state,
        status=frame.status,
        available_feature_ids=tuple(
            feature.feature_id for feature in frame.features if feature.status == "AVAILABLE"
        ),
        unavailable_feature_ids=tuple(
            feature.feature_id for feature in frame.features if feature.status == "UNAVAILABLE"
        ),
        oi_change_verified=(
            "FUTURES_OI_CHANGE_PCT" in available and "FUTURES_OI_DELTA" in available
        ),
        volume_change_verified="FUTURES_VOLUME_CHANGE_PCT" in available,
        candle_vwap_estimate_available="FUTURES_CANDLE_VWAP_ESTIMATE" in available,
        blockers=frame.blockers,
    )


def _alignment(
    results: tuple[X4ResultV1, ...],
    missing: tuple[str, ...],
) -> str:
    # Never manufacture alignment from only the surviving timeframes or missing OI.
    if (
        missing
        or len(results) < 2
        or any(
            result.status == "UNAVAILABLE" or result.positioning_state == "UNKNOWN"
            for result in results
        )
    ):
        return "INSUFFICIENT_DATA"
    states = {result.positioning_state for result in results}
    if states <= _UP_STATES:
        return "CONSISTENT_UP"
    if states <= _DOWN_STATES:
        return "CONSISTENT_DOWN"
    if states == {"FLAT"}:
        return "FLAT"
    return "MIXED"


def compose_x4_multi_timeframe_v1(
    *,
    contract: X4ContractV1,
    captures: Mapping[str, X4AdaptedCandlesV1],
    required_timeframes: tuple[str, ...],
    max_age_seconds_by_timeframe: Mapping[str, float],
    as_of: datetime,
    basis_reference: X4BasisReferenceV1 | None = None,
) -> X4MultiTimeframeResultV1:
    """Compose a single as-of, same-contract/session research snapshot.

    The caller supplies verification-backed B1 captures and explicit freshness
    budgets. Missing frames are reported rather than silently imputed. Output
    alignment never creates execution, risk, position or certification authority.
    """
    if not isinstance(contract, X4ContractV1) or not _aware(as_of):
        raise ValueError("Canonical X4 contract and aware as_of are required")
    if (
        type(required_timeframes) is not tuple
        or len(required_timeframes) < 2
        or len(set(required_timeframes)) != len(required_timeframes)
        or any(tf not in _INTERVALS for tf in required_timeframes)
    ):
        raise ValueError("At least two distinct supported timeframes are required")
    expected = set(required_timeframes)
    if not isinstance(captures, Mapping) or not set(captures) <= expected:
        raise ValueError("Unexpected capture timeframes")
    if (
        not isinstance(max_age_seconds_by_timeframe, Mapping)
        or set(max_age_seconds_by_timeframe) != expected
    ):
        raise ValueError("Provide an explicit freshness budget per required timeframe")
    if any(
        type(budget) not in (float, int) or not math.isfinite(budget) or budget <= 0
        for budget in max_age_seconds_by_timeframe.values()
    ):
        raise ValueError("Freshness budgets must be positive finite numbers")
    if basis_reference is not None and not isinstance(basis_reference, X4BasisReferenceV1):
        raise ValueError("Basis reference must use the X4 contract")

    results: list[X4ResultV1] = []
    evidence: list[X4TimeframeEvidenceV1] = []
    missing = tuple(tf for tf in required_timeframes if tf not in captures)
    session_id: str | None = None
    capture_ids: set[str] = set()
    for tf in required_timeframes:
        if tf not in captures:
            continue
        capture = captures[tf]
        if not isinstance(capture, X4AdaptedCandlesV1):
            raise ValueError("Only verified B1 adapted captures are accepted")
        if (
            capture.contract != contract
            or capture.as_of != as_of
            or capture.data_only is not True
            or capture.live_execution_eligible is not False
            or not capture.samples
            or any(sample.timeframe != tf for sample in capture.samples)
        ):
            raise ValueError("Contract, timeframe or as-of capture mismatch")
        if capture.capture_id in capture_ids:
            raise ValueError("Capture identifiers must be distinct across timeframes")
        capture_ids.add(capture.capture_id)
        first_session = capture.samples[0].session_id
        if session_id is None:
            session_id = first_session
        if session_id != first_session:
            raise ValueError("Mixed futures sessions are prohibited")
        result = analyze_futures_v1(
            contract=contract,
            samples=capture.samples,
            as_of=as_of,
            max_age_seconds=max_age_seconds_by_timeframe[tf],
            basis_reference=basis_reference,
        )
        results.append(result)
        evidence.append(_evidence(result, capture.capture_id))

    frames = tuple(results)
    blockers = tuple(
        [f"MISSING_TIMEFRAME:{tf}" for tf in missing]
        + [f"{frame.timeframe}:{blocker}" for frame in frames for blocker in frame.blockers]
    )
    if not frames or all(frame.status == "UNAVAILABLE" for frame in frames):
        status = "UNAVAILABLE"
    elif missing or any(frame.status != "AVAILABLE" for frame in frames):
        status = "PARTIAL"
    else:
        status = "AVAILABLE"
    return X4MultiTimeframeResultV1(
        market=contract.market,
        instrument_id=contract.canonical_instrument_id,
        provider_symbol=contract.provider_symbol,
        session_id=session_id or "NO_VERIFIED_CAPTURE",
        as_of=as_of,
        required_timeframes=required_timeframes,
        timeframe_results=frames,
        evidence=tuple(evidence),
        missing_timeframes=missing,
        alignment=_alignment(frames, missing),
        status=status,
        blockers=blockers,
    )

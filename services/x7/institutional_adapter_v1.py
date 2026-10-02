"""Offline, provider-neutral FII/DII cash-equity flow adapter for X7.

Consumes exact normalized records plus caller-supplied source attestations. Source
proof objects are *assertions*, not authentication of a publisher. This bridge
neither fetches FII/DII data nor infers derivative or MCX positioning.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime

from services.x7.contracts_v1 import (
    INDEX_MARKETS,
    X7InstitutionalFlowV1,
    _authority,
    _aware,
    _markets,
    _number,
    _text,
    canonical_sha256,
)

_RAW_KEYS = frozenset(
    {
        "trading_date",
        "applicable_markets",
        "flow_unit",
        "source_id",
        "source_record_id",
        "observed_at",
        "published_at",
        "available_at",
        "publication_state",
        "fii_net",
        "dii_net",
    }
)
_PUBLICATION_STATES = frozenset({"FINAL", "PROVISIONAL", "UNAVAILABLE"})
_COMPLETENESS = frozenset({"COMPLETE", "PARTIAL", "UNAVAILABLE"})


def _hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _positive_finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


@dataclass(frozen=True, slots=True)
class X7InstitutionalSourceProofV1:
    """Independent *caller-supplied* record/units/timestamp attestation.

    A correctly formed proof cannot demonstrate that a publisher was genuine;
    independent source verification belongs to the upstream data-acquisition gate.
    """

    trading_date: date
    applicable_markets: tuple[str, ...]
    flow_unit: str
    source_id: str
    source_record_id: str
    observed_at: datetime
    published_at: datetime | None
    available_at: datetime | None
    publication_state: str
    source_verified: bool
    timestamp_semantics_verified: bool
    value_unit_verified: bool
    values_verified: bool
    schema_version: str = "X7_INSTITUTIONAL_SOURCE_PROOF_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if type(self.trading_date) is not date:
            raise ValueError("Exact institutional trading date is required")
        if not _markets(self.applicable_markets) or any(
            market not in INDEX_MARKETS for market in self.applicable_markets
        ):
            raise ValueError("Cash-equity flow applies only to explicit index markets")
        if self.flow_unit != "CRORE_INR":
            raise ValueError("Cash-flow units must be verified crore INR")
        if not _text(self.source_id) or not _text(self.source_record_id):
            raise ValueError("Exact source and source-record IDs are required")
        if not _aware(self.observed_at) or self.observed_at.date() < self.trading_date:
            raise ValueError("Observed time cannot precede the flow trading date")
        if self.published_at is not None and (
            not _aware(self.published_at) or self.published_at < self.observed_at
        ):
            raise ValueError("Publication must follow the observation")
        if self.available_at is not None and (
            not _aware(self.available_at)
            or self.published_at is None
            or self.available_at < self.published_at
        ):
            raise ValueError("Availability must follow the publication")
        if self.publication_state not in _PUBLICATION_STATES:
            raise ValueError("Unsupported institutional publication state")
        for flag in (
            self.source_verified,
            self.timestamp_semantics_verified,
            self.value_unit_verified,
            self.values_verified,
        ):
            if type(flag) is not bool:
                raise ValueError("Attestation flags must be exact booleans")
        if self.source_verified and (
            not self.timestamp_semantics_verified
            or self.published_at is None
            or self.available_at is None
        ):
            raise ValueError("Source verification requires verified time semantics")
        if self.values_verified and (not self.source_verified or not self.value_unit_verified):
            raise ValueError("Value verification requires verified source and units")
        _authority(self, "X7_INSTITUTIONAL_SOURCE_PROOF_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True, slots=True)
class X7InstitutionalAdaptedFlowV1:
    """One fact, with explicit missing-field/finality flags and source hashes."""

    flow: X7InstitutionalFlowV1
    source_record_id: str
    raw_record_sha256: str
    proof_sha256: str
    as_of: datetime
    max_age_seconds: float
    data_completeness: str
    schema_version: str = "X7_INSTITUTIONAL_ADAPTED_FLOW_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.flow, X7InstitutionalFlowV1)
            or not _text(self.source_record_id)
            or not _hash(self.raw_record_sha256)
            or not _hash(self.proof_sha256)
            or not _aware(self.as_of)
            or not _positive_finite(self.max_age_seconds)
            or self.data_completeness not in _COMPLETENESS
        ):
            raise ValueError("Invalid adapted institutional flow/provenance")
        if self.flow.observed_at > self.as_of or (
            self.flow.available_at is not None and self.flow.available_at > self.as_of
        ):
            raise ValueError("Adapted flow cannot introduce future evidence")
        completeness = (
            "COMPLETE"
            if self.flow.fii_net is not None and self.flow.dii_net is not None
            else "PARTIAL"
            if self.flow.fii_net is not None or self.flow.dii_net is not None
            else "UNAVAILABLE"
        )
        if self.data_completeness != completeness:
            raise ValueError("Completeness cannot hide missing FII/DII measurements")
        _authority(self, "X7_INSTITUTIONAL_ADAPTED_FLOW_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True, slots=True)
class X7InstitutionalBatchV1:
    market: str
    session_id: str
    capture_id: str
    as_of: datetime
    flows: tuple[X7InstitutionalAdaptedFlowV1, ...]
    input_sha256: str
    schema_version: str = "X7_INSTITUTIONAL_BATCH_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.market not in INDEX_MARKETS
            or not _text(self.session_id)
            or not _text(self.capture_id)
            or not _aware(self.as_of)
            or not _hash(self.input_sha256)
            or type(self.flows) is not tuple
            or any(not isinstance(row, X7InstitutionalAdaptedFlowV1) for row in self.flows)
        ):
            raise ValueError("Invalid index-only institutional batch")
        dates = tuple(row.flow.trading_date for row in self.flows)
        if dates != tuple(sorted(dates)) or len(set(dates)) != len(dates):
            raise ValueError("Institutional batch requires distinct date-sorted facts")
        if len({row.source_record_id for row in self.flows}) != len(self.flows):
            raise ValueError("Duplicate institutional source-record identity")
        if any(
            row.as_of != self.as_of or self.market not in row.flow.applicable_markets
            for row in self.flows
        ):
            raise ValueError("Institutional fact does not match the target capture")
        _authority(self, "X7_INSTITUTIONAL_BATCH_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def adapt_x7_institutional_flow_v1(
    *,
    raw_record: Mapping[str, object],
    proof: X7InstitutionalSourceProofV1,
    as_of: datetime,
    max_age_seconds: float,
) -> X7InstitutionalAdaptedFlowV1:
    """Adapt an exact captured record with no currency/finality/time inference."""
    if not isinstance(raw_record, Mapping) or set(raw_record) != _RAW_KEYS:
        raise ValueError("Institutional raw record must have the exact normalized fields")
    if not isinstance(proof, X7InstitutionalSourceProofV1) or not _aware(as_of):
        raise TypeError("Typed source attestation and aware as_of required")
    if not _positive_finite(max_age_seconds):
        raise ValueError("Explicit positive finite freshness budget is required")
    for field in (
        "trading_date",
        "applicable_markets",
        "flow_unit",
        "source_id",
        "source_record_id",
        "observed_at",
        "published_at",
        "available_at",
        "publication_state",
    ):
        if raw_record[field] != getattr(proof, field):
            raise ValueError(f"Institutional record conflicts with {field} proof")
    if (
        proof.observed_at > as_of
        or (proof.published_at is not None and proof.published_at > as_of)
        or (proof.available_at is not None and proof.available_at > as_of)
    ):
        raise ValueError("Future or not-yet-published institutional data are prohibited")
    fii, dii = raw_record["fii_net"], raw_record["dii_net"]
    for field, value in (("fii_net", fii), ("dii_net", dii)):
        if value is not None and not _number(value, signed=True):
            raise ValueError(f"{field} must be a finite signed amount in crore INR")
    if proof.values_verified and fii is None and dii is None:
        raise ValueError("Cannot verify missing FII/DII values")
    completeness = (
        "COMPLETE"
        if fii is not None and dii is not None
        else "PARTIAL"
        if fii is not None or dii is not None
        else "UNAVAILABLE"
    )
    final_verified = (
        proof.source_verified
        and proof.value_unit_verified
        and proof.values_verified
        and proof.publication_state == "FINAL"
        and completeness != "UNAVAILABLE"
    )
    if completeness == "UNAVAILABLE":
        status = "UNAVAILABLE"
    elif not final_verified:
        status = "UNVERIFIED"
    elif (as_of - proof.observed_at).total_seconds() > max_age_seconds:
        status = "STALE"
    else:
        status = "AVAILABLE"
    flow = X7InstitutionalFlowV1(
        trading_date=proof.trading_date,
        applicable_markets=proof.applicable_markets,
        flow_unit=proof.flow_unit,
        source_id=proof.source_id,
        observed_at=proof.observed_at,
        published_at=proof.published_at,
        available_at=proof.available_at,
        source_verified=proof.source_verified,
        fii_net=fii,
        dii_net=dii,
        values_verified=final_verified,
        publication_state=proof.publication_state,
        status=status,
    )
    return X7InstitutionalAdaptedFlowV1(
        flow=flow,
        source_record_id=proof.source_record_id,
        raw_record_sha256=canonical_sha256(dict(raw_record)),
        proof_sha256=proof.sha256(),
        as_of=as_of,
        max_age_seconds=max_age_seconds,
        data_completeness=completeness,
    )


def adapt_x7_institutional_batch_v1(
    *,
    market: str,
    session_id: str,
    capture_id: str,
    as_of: datetime,
    raw_records: tuple[Mapping[str, object], ...],
    proofs: tuple[X7InstitutionalSourceProofV1, ...],
    max_age_seconds: float,
) -> X7InstitutionalBatchV1:
    """Build one sorted, date-deduplicated index context; never a directional vote."""
    if market not in INDEX_MARKETS or not _text(session_id) or not _text(capture_id):
        raise ValueError("Institutional cash-equity batch is NIFTY/SENSEX only")
    if not _aware(as_of) or type(raw_records) is not tuple or type(proofs) is not tuple:
        raise ValueError("Aware as_of and exact record/proof tuples are required")
    if len(raw_records) != len(proofs) or not _positive_finite(max_age_seconds):
        raise ValueError("Each institutional record needs its own proof and freshness budget")
    if any(not isinstance(p, X7InstitutionalSourceProofV1) for p in proofs):
        raise TypeError("Every institutional proof must be a typed attestation")
    if len({p.trading_date for p in proofs}) != len(proofs) or len(
        {p.source_record_id for p in proofs}
    ) != len(proofs):
        raise ValueError("Duplicate trading date or source-record ID")
    if any(market not in p.applicable_markets for p in proofs):
        raise ValueError("Institutional record is not applicable to target index")
    rows = tuple(
        adapt_x7_institutional_flow_v1(
            raw_record=raw,
            proof=proof,
            as_of=as_of,
            max_age_seconds=max_age_seconds,
        )
        for raw, proof in zip(raw_records, proofs, strict=True)
    )
    rows = tuple(sorted(rows, key=lambda row: row.flow.trading_date))
    return X7InstitutionalBatchV1(
        market=market,
        session_id=session_id,
        capture_id=capture_id,
        as_of=as_of,
        flows=rows,
        input_sha256=canonical_sha256(
            {
                "records": [row.raw_record_sha256 for row in rows],
                "proofs": [row.proof_sha256 for row in rows],
                "age_budget_seconds": max_age_seconds,
            }
        ),
    )


__all__ = [
    "X7InstitutionalSourceProofV1",
    "X7InstitutionalAdaptedFlowV1",
    "X7InstitutionalBatchV1",
    "adapt_x7_institutional_flow_v1",
    "adapt_x7_institutional_batch_v1",
]

"""Offline X7 replay from retained exact normalized records and source proofs.

Replaying a historical artifact never changes its original point-in-time status.
Checks prove internal reproducibility, not upstream publisher authenticity.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime

from services.x7.contracts_v1 import MARKETS, _authority, _aware, _sha, canonical_sha256
from services.x7.event_adapter_v1 import (
    X7EventSourceProofV1,
    adapt_x7_scheduled_event_batch_v1,
)
from services.x7.global_adapter_v1 import (
    X7GlobalSourceProofV1,
    adapt_x7_global_batch_v1,
)
from services.x7.institutional_adapter_v1 import (
    X7InstitutionalSourceProofV1,
    adapt_x7_institutional_batch_v1,
)
from services.x7.research_view_v1 import (
    X7ResearchViewV1,
    build_x7_research_view_v1,
)


@dataclass(frozen=True, slots=True)
class X7ReplayCheckV1:
    market: str
    session_id: str
    capture_id: str
    as_of: datetime
    original_view_sha256: str
    reconstructed_view_sha256: str
    source_manifest_sha256: str
    status: str = "MATCH"
    schema_version: str = "X7_REPLAY_CHECK_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.market not in MARKETS
            or not self.session_id
            or not self.capture_id
            or not _aware(self.as_of)
            or not all(
                _sha(x)
                for x in (
                    self.original_view_sha256,
                    self.reconstructed_view_sha256,
                    self.source_manifest_sha256,
                )
            )
            or self.original_view_sha256 != self.reconstructed_view_sha256
            or self.status != "MATCH"
        ):
            raise ValueError("Replay check must match exact retained evidence")
        _authority(self, "X7_REPLAY_CHECK_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def replay_x7_research_view_v1(
    *,
    view: X7ResearchViewV1,
    expected_view_sha256: str,
    global_raw_records: tuple[Mapping[str, object], ...],
    global_proofs: tuple[X7GlobalSourceProofV1, ...],
    global_max_age_seconds_by_name: Mapping[str, float],
    institutional_raw_records: tuple[Mapping[str, object], ...] = (),
    institutional_proofs: tuple[X7InstitutionalSourceProofV1, ...] = (),
    event_raw_records: tuple[Mapping[str, object], ...] = (),
    event_proofs: tuple[X7EventSourceProofV1, ...] = (),
) -> X7ReplayCheckV1:
    """Recreate every present batch and research view; mismatch raises, not votes."""
    if not isinstance(view, X7ResearchViewV1) or not _sha(expected_view_sha256):
        raise TypeError("Typed view and retained external SHA-256 anchor required")
    if view.sha256() != expected_view_sha256:
        raise ValueError("Persisted view has changed relative to its external checksum")
    if (
        type(global_raw_records) is not tuple
        or type(global_proofs) is not tuple
        or type(institutional_raw_records) is not tuple
        or type(institutional_proofs) is not tuple
        or type(event_raw_records) is not tuple
        or type(event_proofs) is not tuple
    ):
        raise TypeError("Replay requires exact immutable raw/proof tuples")
    c = view.capture
    common = dict(market=c.market, session_id=c.session_id, capture_id=c.capture_id, as_of=c.as_of)
    global_batch = adapt_x7_global_batch_v1(
        **common,
        raw_records=global_raw_records,
        proofs=global_proofs,
        max_age_seconds_by_name=global_max_age_seconds_by_name,
    )
    if global_batch.sha256() != view.global_batch_sha256:
        raise ValueError("Global replay does not reproduce the original batch")
    if view.institutional_batch_sha256 is None:
        if institutional_raw_records or institutional_proofs:
            raise ValueError("Cannot introduce absent institutional evidence during replay")
        institutional_batch = None
    else:
        institutional_batch = adapt_x7_institutional_batch_v1(
            **common,
            raw_records=institutional_raw_records,
            proofs=institutional_proofs,
            max_age_seconds=view.institutional_max_age_seconds,
        )
        if institutional_batch.sha256() != view.institutional_batch_sha256:
            raise ValueError("Institutional replay does not reproduce the original batch")
    if view.event_batch_sha256 is None:
        if event_raw_records or event_proofs:
            raise ValueError("Cannot introduce absent calendar evidence during replay")
        event_batch = None
    else:
        event_batch = adapt_x7_scheduled_event_batch_v1(
            **common,
            raw_records=event_raw_records,
            proofs=event_proofs,
            max_age_seconds=view.event_max_age_seconds,
        )
        if event_batch.sha256() != view.event_batch_sha256:
            raise ValueError("Event replay does not reproduce the original batch")
    reconstructed = build_x7_research_view_v1(
        global_batch=global_batch,
        institutional_batch=institutional_batch,
        event_batch=event_batch,
        capture_verified=c.capture_verified,
        point_in_time_verified=c.point_in_time_verified,
        historical_retrieval=c.historical_retrieval,
        global_max_age_seconds=view.global_max_age_seconds,
        institutional_max_age_seconds=view.institutional_max_age_seconds,
        event_max_age_seconds=view.event_max_age_seconds,
    )
    if reconstructed != view or reconstructed.sha256() != expected_view_sha256:
        raise ValueError("Research view, original time status or provenance does not replay")
    return X7ReplayCheckV1(
        market=c.market,
        session_id=c.session_id,
        capture_id=c.capture_id,
        as_of=c.as_of,
        original_view_sha256=expected_view_sha256,
        reconstructed_view_sha256=reconstructed.sha256(),
        source_manifest_sha256=reconstructed.provenance_sha256,
    )


@dataclass(frozen=True, slots=True)
class X7ReplayTimelineV1:
    view_hashes: tuple[str, ...]
    retrospective_view_hashes: tuple[str, ...]
    manifest_sha256: str
    schema_version: str = "X7_REPLAY_TIMELINE_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.view_hashes) is not tuple
            or type(self.retrospective_view_hashes) is not tuple
            or any(
                not _sha(x)
                for x in (
                    *self.view_hashes,
                    *self.retrospective_view_hashes,
                    self.manifest_sha256,
                )
            )
            or len(set(self.view_hashes)) != len(self.view_hashes)
            or any(x not in self.view_hashes for x in self.retrospective_view_hashes)
            or self.manifest_sha256
            != canonical_sha256(
                {
                    "view_hashes": self.view_hashes,
                    "retrospective_view_hashes": self.retrospective_view_hashes,
                }
            )
        ):
            raise ValueError("Invalid deterministic X7 replay timeline")
        _authority(self, "X7_REPLAY_TIMELINE_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def audit_x7_replay_timeline_v1(
    *,
    views: tuple[X7ResearchViewV1, ...],
    expected_view_hashes: tuple[str, ...],
) -> X7ReplayTimelineV1:
    """Check ordered snapshots and external hashes; *not* a source re-adaptation."""
    if type(views) is not tuple or type(expected_view_hashes) is not tuple:
        raise TypeError("Timeline requires immutable ordered views and external hashes")
    if len(views) != len(expected_view_hashes):
        raise ValueError("Every timeline view needs its own retained checksum")
    latest: dict[str, datetime] = {}
    identities: set[tuple[str, str, str]] = set()
    retrospective = []
    for view, expected in zip(views, expected_view_hashes, strict=True):
        if (
            not isinstance(view, X7ResearchViewV1)
            or not _sha(expected)
            or view.sha256() != expected
        ):
            raise ValueError("Timeline view changed or has no exact external checksum")
        c = view.capture
        identity = (c.market, c.session_id, c.capture_id)
        if identity in identities:
            raise ValueError("Duplicate market/session/capture identity")
        identities.add(identity)
        if c.market in latest and c.as_of <= latest[c.market]:
            raise ValueError("Same-market replay is out of order or repeats an instant")
        latest[c.market] = c.as_of
        if c.historical_retrieval or not c.point_in_time_verified:
            retrospective.append(expected)
    return X7ReplayTimelineV1(
        view_hashes=expected_view_hashes,
        retrospective_view_hashes=tuple(retrospective),
        manifest_sha256=canonical_sha256(
            {
                "view_hashes": expected_view_hashes,
                "retrospective_view_hashes": tuple(retrospective),
            }
        ),
    )


__all__ = [
    "X7ReplayCheckV1",
    "X7ReplayTimelineV1",
    "replay_x7_research_view_v1",
    "audit_x7_replay_timeline_v1",
]

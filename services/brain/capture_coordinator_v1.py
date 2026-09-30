"""Zero-authority snapshot capture coordinator.

This module accepts source values that were already produced elsewhere.
It performs no market-data, provider, broker, decision, execution, risk,
position-management, or certification work.

Flow:

    existing source objects
        -> frozen B2 source adapters
        -> MarketSnapshotV1
        -> frozen B3 snapshot journal
        -> CaptureResultV1 read model
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from services.brain.market_snapshot_v1 import (
    MarketSnapshotV1,
    build_market_snapshot_v1,
)
from services.brain.snapshot_journal_v1 import (
    SnapshotJournalEntryV1,
    capture_snapshot_v1,
)
from services.brain.source_adapters_v1 import (
    IndexBreadthSourceV1,
    IndexNewsSourceV1,
    IndexOptionChainSourceV1,
    IndexPremarketSourceV1,
    IndexTechnicalSourceV1,
    McxEventRiskSourceV1,
    McxNativeSourceV1,
    adapt_index_breadth_v1,
    adapt_index_news_v1,
    adapt_index_option_chain_v1,
    adapt_index_premarket_v1,
    adapt_index_technical_v1,
    adapt_mcx_event_risk_v1,
    adapt_mcx_native_v1,
)


CAPTURE_COORDINATOR_RESULT_SCHEMA_V1 = (
    "BRAIN_CAPTURE_COORDINATOR_RESULT_V1"
)

INDEX_CAPTURE_MARKETS = frozenset(
    {
        "NIFTY",
        "SENSEX",
    }
)

MCX_CAPTURE_MARKETS = frozenset(
    {
        "CRUDEOILM",
        "GOLDM",
        "NATGASMINI",
    }
)


def _require_text(
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(
            f"{name} must be a non-empty trimmed string."
        )

    return value


def _require_aware_datetime(
    name: str,
    value: object,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{name} must be timezone-aware."
        )

    return value


def _require_source_market(
    *,
    name: str,
    source: object,
    market: str,
) -> None:
    source_market = getattr(
        source,
        "market",
        None,
    )

    if source_market != market:
        raise ValueError(
            f"{name}.market must equal capture market {market!r}; "
            f"got {source_market!r}."
        )


@dataclass(
    frozen=True,
    slots=True,
)
class IndexCaptureSourcesV1:
    """Already-produced index source values accepted by the coordinator."""

    premarket: IndexPremarketSourceV1 | None = None
    news: IndexNewsSourceV1 | None = None
    technical: IndexTechnicalSourceV1 | None = None
    breadth: IndexBreadthSourceV1 | None = None
    option_chain: IndexOptionChainSourceV1 | None = None

    def __post_init__(self) -> None:
        declarations = (
            (
                "premarket",
                self.premarket,
                IndexPremarketSourceV1,
            ),
            (
                "news",
                self.news,
                IndexNewsSourceV1,
            ),
            (
                "technical",
                self.technical,
                IndexTechnicalSourceV1,
            ),
            (
                "breadth",
                self.breadth,
                IndexBreadthSourceV1,
            ),
            (
                "option_chain",
                self.option_chain,
                IndexOptionChainSourceV1,
            ),
        )

        supplied = False

        for name, value, expected_type in declarations:
            if value is None:
                continue

            supplied = True

            if not isinstance(value, expected_type):
                raise TypeError(
                    f"{name} must be {expected_type.__name__} or None."
                )

        if not supplied:
            raise ValueError(
                "IndexCaptureSourcesV1 requires at least one source."
            )


@dataclass(
    frozen=True,
    slots=True,
)
class McxCaptureSourcesV1:
    """Already-produced MCX source values accepted by the coordinator."""

    native: McxNativeSourceV1 | None = None
    event_risk: McxEventRiskSourceV1 | None = None

    def __post_init__(self) -> None:
        declarations = (
            (
                "native",
                self.native,
                McxNativeSourceV1,
            ),
            (
                "event_risk",
                self.event_risk,
                McxEventRiskSourceV1,
            ),
        )

        supplied = False

        for name, value, expected_type in declarations:
            if value is None:
                continue

            supplied = True

            if not isinstance(value, expected_type):
                raise TypeError(
                    f"{name} must be {expected_type.__name__} or None."
                )

        if not supplied:
            raise ValueError(
                "McxCaptureSourcesV1 requires at least one source."
            )


@dataclass(
    frozen=True,
    slots=True,
)
class CaptureResultV1:
    """Immutable read model describing one completed journal capture."""

    session_id: str
    market: str
    snapshot_at: datetime
    snapshot_sha256: str
    journal_entry_sha256: str
    record_relpath: str

    analyzer_ids: tuple[str, ...]
    expected_production_analyzers: tuple[str, ...]
    present_production_analyzers: tuple[str, ...]
    missing_production_analyzers: tuple[str, ...]

    production_coverage_pct: float
    production_complete: bool

    evidence_status_counts: tuple[
        tuple[str, int],
        ...
    ]

    freshness_counts: tuple[
        tuple[str, int],
        ...
    ]

    source_strategy_version: str
    source_policy_epoch: str
    source_runtime_ref: str

    execution_authority: bool = False
    decision_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False

    schema_version: str = (
        CAPTURE_COORDINATOR_RESULT_SCHEMA_V1
    )

    def __post_init__(self) -> None:
        _require_text(
            "session_id",
            self.session_id,
        )

        _require_text(
            "market",
            self.market,
        )

        _require_aware_datetime(
            "snapshot_at",
            self.snapshot_at,
        )

        for name in (
            "snapshot_sha256",
            "journal_entry_sha256",
        ):
            value = getattr(self, name)

            if (
                len(value) != 64
                or value != value.lower()
            ):
                raise ValueError(
                    f"{name} must be 64 lowercase hex characters."
                )

            try:
                int(value, 16)
            except ValueError as exc:
                raise ValueError(
                    f"{name} must be hexadecimal."
                ) from exc

        _require_text(
            "record_relpath",
            self.record_relpath,
        )

        for name in (
            "source_strategy_version",
            "source_policy_epoch",
            "source_runtime_ref",
        ):
            _require_text(
                name,
                getattr(self, name),
            )

        if self.schema_version != (
            CAPTURE_COORDINATOR_RESULT_SCHEMA_V1
        ):
            raise ValueError(
                "unsupported capture result schema."
            )

        for name in (
            "execution_authority",
            "decision_authority",
            "risk_authority",
            "position_authority",
            "certification_authority",
        ):
            if getattr(self, name) is not False:
                raise ValueError(
                    f"{name} is permanently False in CaptureResultV1."
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version":
                self.schema_version,
            "session_id":
                self.session_id,
            "market":
                self.market,
            "snapshot_at":
                self.snapshot_at.isoformat(),
            "snapshot_sha256":
                self.snapshot_sha256,
            "journal_entry_sha256":
                self.journal_entry_sha256,
            "record_relpath":
                self.record_relpath,
            "analyzer_ids":
                list(self.analyzer_ids),
            "expected_production_analyzers":
                list(self.expected_production_analyzers),
            "present_production_analyzers":
                list(self.present_production_analyzers),
            "missing_production_analyzers":
                list(self.missing_production_analyzers),
            "production_coverage_pct":
                self.production_coverage_pct,
            "production_complete":
                self.production_complete,
            "evidence_status_counts":
                dict(self.evidence_status_counts),
            "freshness_counts":
                dict(self.freshness_counts),
            "source_strategy_version":
                self.source_strategy_version,
            "source_policy_epoch":
                self.source_policy_epoch,
            "source_runtime_ref":
                self.source_runtime_ref,
            "execution_authority":
                False,
            "decision_authority":
                False,
            "risk_authority":
                False,
            "position_authority":
                False,
            "certification_authority":
                False,
        }


def _capture_result(
    *,
    session_id: str,
    snapshot: MarketSnapshotV1,
    entry: SnapshotJournalEntryV1,
) -> CaptureResultV1:
    return CaptureResultV1(
        session_id=session_id,
        market=snapshot.market,
        snapshot_at=snapshot.snapshot_at,
        snapshot_sha256=snapshot.snapshot_sha256,
        journal_entry_sha256=entry.entry_sha256,
        record_relpath=entry.record_relpath,
        analyzer_ids=snapshot.analyzer_ids,
        expected_production_analyzers=(
            snapshot.expected_production_analyzers
        ),
        present_production_analyzers=(
            snapshot.production_analyzer_ids_present
        ),
        missing_production_analyzers=(
            snapshot.missing_production_analyzers
        ),
        production_coverage_pct=(
            snapshot.production_coverage_pct
        ),
        production_complete=(
            snapshot.production_complete
        ),
        evidence_status_counts=tuple(
            sorted(
                snapshot.evidence_status_counts().items()
            )
        ),
        freshness_counts=tuple(
            sorted(
                snapshot.freshness_counts().items()
            )
        ),
        source_strategy_version=(
            snapshot.source_strategy_version
        ),
        source_policy_epoch=(
            snapshot.source_policy_epoch
        ),
        source_runtime_ref=(
            snapshot.source_runtime_ref
        ),
    )


def capture_index_sources_v1(
    *,
    journal_root: str | Path,
    session_id: str,
    market: str,
    snapshot_at: datetime,
    generated_at: datetime,
    sources: IndexCaptureSourcesV1,
    source_strategy_version: str,
    source_policy_epoch: str,
    source_runtime_ref: str,
) -> CaptureResultV1:
    """Adapt already-produced index sources and persist one snapshot."""

    if market not in INDEX_CAPTURE_MARKETS:
        raise ValueError(
            f"index capture market must be one of "
            f"{sorted(INDEX_CAPTURE_MARKETS)}; got {market!r}."
        )

    if not isinstance(sources, IndexCaptureSourcesV1):
        raise TypeError(
            "sources must be IndexCaptureSourcesV1."
        )

    _require_aware_datetime(
        "snapshot_at",
        snapshot_at,
    )

    _require_aware_datetime(
        "generated_at",
        generated_at,
    )

    _require_text(
        "source_strategy_version",
        source_strategy_version,
    )

    _require_text(
        "source_policy_epoch",
        source_policy_epoch,
    )

    _require_text(
        "source_runtime_ref",
        source_runtime_ref,
    )

    results = []

    if sources.premarket is not None:
        _require_source_market(
            name="premarket",
            source=sources.premarket,
            market=market,
        )

        results.extend(
            adapt_index_premarket_v1(
                sources.premarket
            )
        )

    if sources.news is not None:
        _require_source_market(
            name="news",
            source=sources.news,
            market=market,
        )

        results.append(
            adapt_index_news_v1(
                sources.news
            )
        )

    if sources.technical is not None:
        _require_source_market(
            name="technical",
            source=sources.technical,
            market=market,
        )

        results.extend(
            adapt_index_technical_v1(
                sources.technical
            )
        )

    if sources.breadth is not None:
        _require_source_market(
            name="breadth",
            source=sources.breadth,
            market=market,
        )

        results.append(
            adapt_index_breadth_v1(
                sources.breadth
            )
        )

    if sources.option_chain is not None:
        _require_source_market(
            name="option_chain",
            source=sources.option_chain,
            market=market,
        )

        results.append(
            adapt_index_option_chain_v1(
                sources.option_chain
            )
        )

    snapshot = build_market_snapshot_v1(
        market=market,
        snapshot_at=snapshot_at,
        generated_at=generated_at,
        analyzer_results=tuple(results),
        source_strategy_version=(
            source_strategy_version
        ),
        source_policy_epoch=(
            source_policy_epoch
        ),
        source_runtime_ref=(
            source_runtime_ref
        ),
    )

    entry = capture_snapshot_v1(
        journal_root=journal_root,
        session_id=session_id,
        snapshot=snapshot,
    )

    return _capture_result(
        session_id=session_id,
        snapshot=snapshot,
        entry=entry,
    )


def capture_mcx_sources_v1(
    *,
    journal_root: str | Path,
    session_id: str,
    market: str,
    snapshot_at: datetime,
    generated_at: datetime,
    sources: McxCaptureSourcesV1,
    source_strategy_version: str,
    source_policy_epoch: str,
    source_runtime_ref: str,
) -> CaptureResultV1:
    """Adapt already-produced MCX sources and persist one snapshot."""

    if market not in MCX_CAPTURE_MARKETS:
        raise ValueError(
            f"MCX capture market must be one of "
            f"{sorted(MCX_CAPTURE_MARKETS)}; got {market!r}."
        )

    if not isinstance(sources, McxCaptureSourcesV1):
        raise TypeError(
            "sources must be McxCaptureSourcesV1."
        )

    _require_aware_datetime(
        "snapshot_at",
        snapshot_at,
    )

    _require_aware_datetime(
        "generated_at",
        generated_at,
    )

    _require_text(
        "source_strategy_version",
        source_strategy_version,
    )

    _require_text(
        "source_policy_epoch",
        source_policy_epoch,
    )

    _require_text(
        "source_runtime_ref",
        source_runtime_ref,
    )

    results = []

    if sources.native is not None:
        _require_source_market(
            name="native",
            source=sources.native,
            market=market,
        )

        results.extend(
            adapt_mcx_native_v1(
                sources.native
            )
        )

    if sources.event_risk is not None:
        _require_source_market(
            name="event_risk",
            source=sources.event_risk,
            market=market,
        )

        results.append(
            adapt_mcx_event_risk_v1(
                sources.event_risk
            )
        )

    snapshot = build_market_snapshot_v1(
        market=market,
        snapshot_at=snapshot_at,
        generated_at=generated_at,
        analyzer_results=tuple(results),
        source_strategy_version=(
            source_strategy_version
        ),
        source_policy_epoch=(
            source_policy_epoch
        ),
        source_runtime_ref=(
            source_runtime_ref
        ),
    )

    entry = capture_snapshot_v1(
        journal_root=journal_root,
        session_id=session_id,
        snapshot=snapshot,
    )

    return _capture_result(
        session_id=session_id,
        snapshot=snapshot,
        entry=entry,
    )


__all__ = [
    "CAPTURE_COORDINATOR_RESULT_SCHEMA_V1",
    "INDEX_CAPTURE_MARKETS",
    "MCX_CAPTURE_MARKETS",
    "CaptureResultV1",
    "IndexCaptureSourcesV1",
    "McxCaptureSourcesV1",
    "capture_index_sources_v1",
    "capture_mcx_sources_v1",
]

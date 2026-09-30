"""Immutable deterministic market evidence snapshot.

MarketSnapshotV1 captures normalized analyzer observations for one market and
one observation boundary.

It has no execution, decision, risk, position, broker, or certification
authority.

The snapshot identity is a SHA-256 digest of a canonical JSON payload.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Iterable

from services.brain.analyzer_registry_v1 import (
    DEFAULT_ANALYZER_REGISTRY_V1,
    SUPPORTED_MARKETS,
    AnalyzerRegistryV1,
)
from services.contracts.brain_evidence_v1 import (
    AnalyzerResultV1,
)


def _require_text(
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(
            f"{name} must be a non-empty trimmed string."
        )

    return value


def _optional_text(
    name: str,
    value: object,
) -> None:
    if value is None:
        return

    _require_text(
        name,
        value,
    )


def _require_aware_datetime(
    name: str,
    value: object,
) -> datetime:
    if (
        not isinstance(
            value,
            datetime,
        )
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{name} must be timezone-aware."
        )

    return value


def _require_string_tuple(
    name: str,
    values: object,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    if not isinstance(
        values,
        tuple,
    ):
        raise ValueError(
            f"{name} must be a tuple."
        )

    if (
        not allow_empty
        and not values
    ):
        raise ValueError(
            f"{name} must not be empty."
        )

    if any(
        not isinstance(
            value,
            str,
        )
        or not value.strip()
        or value != value.strip()
        for value in values
    ):
        raise ValueError(
            f"{name} entries must be non-empty trimmed strings."
        )

    if len(
        values
    ) != len(
        set(
            values
        )
    ):
        raise ValueError(
            f"{name} must not contain duplicates."
        )

    return values


def _canonical_result_payload(
    result: AnalyzerResultV1,
) -> dict[str, object]:
    payload = result.to_dict()

    evidence = list(
        payload[
            "evidence"
        ]
    )

    for item in evidence:
        item["blockers"] = sorted(
            item.get(
                "blockers",
                [],
            )
        )

        item["warnings"] = sorted(
            item.get(
                "warnings",
                [],
            )
        )

    evidence.sort(
        key=lambda item: str(
            item[
                "evidence_id"
            ]
        )
    )

    payload[
        "evidence"
    ] = evidence

    payload[
        "blockers"
    ] = sorted(
        payload.get(
            "blockers",
            [],
        )
    )

    payload[
        "warnings"
    ] = sorted(
        payload.get(
            "warnings",
            [],
        )
    )

    return payload


@dataclass(
    frozen=True,
    slots=True,
)
class MarketSnapshotV1:
    """Immutable observation packet for one market/time boundary."""

    market: str

    snapshot_at: datetime
    generated_at: datetime

    analyzer_results: tuple[
        AnalyzerResultV1,
        ...,
    ]

    expected_production_analyzers: tuple[
        str,
        ...,
    ]

    registry_schema_version: str

    source_strategy_version: str | None = None
    source_policy_epoch: str | None = None
    source_runtime_ref: str | None = None

    execution_authority: bool = False
    decision_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False

    schema_version: str = "BRAIN_MARKET_SNAPSHOT_V1"

    def __post_init__(
        self,
    ) -> None:
        if self.market not in SUPPORTED_MARKETS:
            raise ValueError(
                f"unsupported market: {self.market}"
            )

        _require_aware_datetime(
            "snapshot_at",
            self.snapshot_at,
        )

        _require_aware_datetime(
            "generated_at",
            self.generated_at,
        )

        _require_text(
            "registry_schema_version",
            self.registry_schema_version,
        )

        _require_text(
            "schema_version",
            self.schema_version,
        )

        for name in (
            "source_strategy_version",
            "source_policy_epoch",
            "source_runtime_ref",
        ):
            _optional_text(
                name,
                getattr(
                    self,
                    name,
                ),
            )

        if not isinstance(
            self.analyzer_results,
            tuple,
        ):
            raise ValueError(
                "analyzer_results must be a tuple."
            )

        _require_string_tuple(
            "expected_production_analyzers",
            self.expected_production_analyzers,
            allow_empty=False,
        )

        if tuple(
            sorted(
                self.expected_production_analyzers
            )
        ) != self.expected_production_analyzers:
            raise ValueError(
                "expected_production_analyzers must be sorted."
            )

        seen: set[str] = set()

        for result in self.analyzer_results:
            if not isinstance(
                result,
                AnalyzerResultV1,
            ):
                raise ValueError(
                    "analyzer_results entries must be AnalyzerResultV1."
                )

            if result.market != self.market:
                raise ValueError(
                    "analyzer result market must match snapshot market."
                )

            if result.analyzer in seen:
                raise ValueError(
                    f"duplicate analyzer result: {result.analyzer}"
                )

            seen.add(
                result.analyzer
            )

            try:
                descriptor = (
                    DEFAULT_ANALYZER_REGISTRY_V1.get(
                        result.analyzer
                    )
                )
            except KeyError as exc:
                raise ValueError(
                    f"unregistered analyzer: {result.analyzer}"
                ) from exc

            if self.market not in descriptor.markets:
                raise ValueError(
                    f"analyzer {result.analyzer} does not support "
                    f"{self.market}"
                )

            if result.execution_authority is not False:
                raise ValueError(
                    "snapshot cannot contain execution-authoritative "
                    "analyzer results."
                )

        for name in (
            "execution_authority",
            "decision_authority",
            "risk_authority",
            "position_authority",
            "certification_authority",
        ):
            if getattr(
                self,
                name,
            ) is not False:
                raise ValueError(
                    f"{name} is permanently False in MarketSnapshotV1."
                )

    @property
    def analyzer_ids(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                result.analyzer
                for result in self.analyzer_results
            )
        )

    @property
    def production_analyzer_ids_present(
        self,
    ) -> tuple[str, ...]:
        expected = set(
            self.expected_production_analyzers
        )

        return tuple(
            analyzer
            for analyzer in self.analyzer_ids
            if analyzer in expected
        )

    @property
    def missing_production_analyzers(
        self,
    ) -> tuple[str, ...]:
        present = set(
            self.analyzer_ids
        )

        return tuple(
            analyzer
            for analyzer
            in self.expected_production_analyzers
            if analyzer not in present
        )

    @property
    def extra_registered_analyzers(
        self,
    ) -> tuple[str, ...]:
        expected = set(
            self.expected_production_analyzers
        )

        return tuple(
            analyzer
            for analyzer in self.analyzer_ids
            if analyzer not in expected
        )

    @property
    def production_coverage_pct(
        self,
    ) -> float:
        expected_count = len(
            self.expected_production_analyzers
        )

        if expected_count == 0:
            return 100.0

        return (
            100.0
            * len(
                self.production_analyzer_ids_present
            )
            / expected_count
        )

    @property
    def production_complete(
        self,
    ) -> bool:
        return not self.missing_production_analyzers

    def evidence_status_counts(
        self,
    ) -> dict[str, int]:
        counter: Counter[str] = Counter()

        for result in self.analyzer_results:
            for evidence in result.evidence:
                counter[
                    evidence.status
                ] += 1

        return dict(
            sorted(
                counter.items()
            )
        )

    def freshness_counts(
        self,
    ) -> dict[str, int]:
        counter: Counter[str] = Counter()

        for result in self.analyzer_results:
            for evidence in result.evidence:
                counter[
                    evidence.freshness
                ] += 1

        return dict(
            sorted(
                counter.items()
            )
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        results = [
            _canonical_result_payload(
                result
            )
            for result in self.analyzer_results
        ]

        results.sort(
            key=lambda item: str(
                item[
                    "analyzer"
                ]
            )
        )

        return {
            "schema_version":
                self.schema_version,

            "market":
                self.market,

            "snapshot_at":
                self.snapshot_at.isoformat(),

            "generated_at":
                self.generated_at.isoformat(),

            "registry_schema_version":
                self.registry_schema_version,

            "expected_production_analyzers":
                list(
                    self.expected_production_analyzers
                ),

            "source_strategy_version":
                self.source_strategy_version,

            "source_policy_epoch":
                self.source_policy_epoch,

            "source_runtime_ref":
                self.source_runtime_ref,

            "analyzer_results":
                results,

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

    def canonical_json(
        self,
    ) -> str:
        return json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            allow_nan=False,
            separators=(
                ",",
                ":",
            ),
            sort_keys=True,
        )

    @property
    def snapshot_sha256(
        self,
    ) -> str:
        return sha256(
            self.canonical_json().encode(
                "utf-8"
            )
        ).hexdigest()

    def to_dict(
        self,
    ) -> dict[str, object]:
        payload = self.canonical_payload()

        payload[
            "snapshot_sha256"
        ] = self.snapshot_sha256

        payload[
            "coverage"
        ] = {
            "expected_production_count":
                len(
                    self.expected_production_analyzers
                ),

            "present_production_count":
                len(
                    self.production_analyzer_ids_present
                ),

            "production_coverage_pct":
                self.production_coverage_pct,

            "production_complete":
                self.production_complete,

            "missing_production_analyzers":
                list(
                    self.missing_production_analyzers
                ),

            "extra_registered_analyzers":
                list(
                    self.extra_registered_analyzers
                ),
        }

        payload[
            "evidence_status_counts"
        ] = self.evidence_status_counts()

        payload[
            "freshness_counts"
        ] = self.freshness_counts()

        return payload


def build_market_snapshot_v1(
    *,
    market: str,
    snapshot_at: datetime,
    generated_at: datetime,
    analyzer_results: Iterable[
        AnalyzerResultV1
    ],
    source_strategy_version: str | None = None,
    source_policy_epoch: str | None = None,
    source_runtime_ref: str | None = None,
    registry: AnalyzerRegistryV1 = DEFAULT_ANALYZER_REGISTRY_V1,
) -> MarketSnapshotV1:
    """Build a snapshot using the production registry expected at capture."""

    if market not in SUPPORTED_MARKETS:
        raise ValueError(
            f"unsupported market: {market}"
        )

    expected = tuple(
        sorted(
            descriptor.analyzer_id
            for descriptor
            in registry.production_inputs(
                market
            )
        )
    )

    return MarketSnapshotV1(
        market=market,
        snapshot_at=snapshot_at,
        generated_at=generated_at,
        analyzer_results=tuple(
            analyzer_results
        ),
        expected_production_analyzers=expected,
        registry_schema_version=registry.schema_version,
        source_strategy_version=source_strategy_version,
        source_policy_epoch=source_policy_epoch,
        source_runtime_ref=source_runtime_ref,
        execution_authority=False,
        decision_authority=False,
        risk_authority=False,
        position_authority=False,
        certification_authority=False,
    )


__all__ = [
    "MarketSnapshotV1",
    "build_market_snapshot_v1",
]
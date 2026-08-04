"""Typed, deterministic diagnostic models for canonical/legacy comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Mapping

from services.contracts.analysis_result_v1 import AnalysisResultV1
from services.contracts.final_decision_v1 import FinalDecisionV1
from services.contracts.market_snapshot_v1 import MarketSnapshotV1


@dataclass(frozen=True, slots=True)
class ComparisonDifference:
    """One semantic difference; never an execution instruction."""

    category: str
    legacy_value: Any
    canonical_value: Any
    severity: str = "INFO"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "legacy_value": self.legacy_value,
            "canonical_value": self.canonical_value,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(slots=True)
class CanonicalLegacyComparison:
    """Side-effect-free comparison of one legacy result and its canonical peer."""

    source: str
    snapshot: MarketSnapshotV1 | None = None
    legacy_decision: FinalDecisionV1 | None = None
    canonical_analysis: AnalysisResultV1 | None = None
    canonical_decision: FinalDecisionV1 | None = None
    differences: tuple[ComparisonDifference, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    trace_metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def comparable(self) -> bool:
        return (
            self.snapshot is not None
            and self.legacy_decision is not None
            and self.canonical_decision is not None
            and not self.errors
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "comparable": self.comparable,
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "legacy_decision": (
                self.legacy_decision.to_dict() if self.legacy_decision else None
            ),
            "canonical_analysis": (
                self.canonical_analysis.to_dict()
                if self.canonical_analysis else None
            ),
            "canonical_decision": (
                self.canonical_decision.to_dict()
                if self.canonical_decision else None
            ),
            "differences": [item.to_dict() for item in self.differences],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "trace_metadata": dict(self.trace_metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

"""Certified composition for ledger-grounded prediction reports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from services.contracts.prediction_performance_report_v1 import (
    PredictionPerformanceReportV1,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_orchestration.prediction_outcome_ledger import (
    PredictionOutcomeLedger,
)
from services.reporting.prediction_performance_report_archive import (
    PredictionPerformanceReportArchive,
)
from services.reporting.prediction_performance_report_builder import (
    build_prediction_performance_report,
)


@dataclass(frozen=True, slots=True)
class CertifiedPredictionReportingCompositionV1:
    """Exact read-only reporting authority for immutable ledgers."""

    prediction_ledger: PredictionLedger
    outcome_ledger: PredictionOutcomeLedger
    archive: PredictionPerformanceReportArchive
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = (
        "certified_prediction_reporting_composition.v1"
    )

    def __post_init__(self) -> None:
        if type(self.prediction_ledger) is not PredictionLedger:
            raise TypeError("prediction_ledger")
        if type(self.outcome_ledger) is not PredictionOutcomeLedger:
            raise TypeError("outcome_ledger")
        if (
            type(self.archive)
            is not PredictionPerformanceReportArchive
        ):
            raise TypeError("archive")
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version
            != "certified_prediction_reporting_composition.v1"
        ):
            raise ValueError(
                "certified reporting must remain PAPER-only and read-only"
            )

    def build(
        self,
        *,
        generated_at: datetime,
        report_id: str,
    ) -> PredictionPerformanceReportV1:
        return build_prediction_performance_report(
            prediction_ledger=self.prediction_ledger,
            outcome_ledger=self.outcome_ledger,
            generated_at=generated_at,
            report_id=report_id,
        )

    def build_and_save(
        self,
        *,
        generated_at: datetime,
        report_id: str,
    ) -> tuple[
        PredictionPerformanceReportV1,
        dict[str, object],
    ]:
        report = self.build(
            generated_at=generated_at,
            report_id=report_id,
        )
        persisted = self.archive.save(report)
        return report, persisted
